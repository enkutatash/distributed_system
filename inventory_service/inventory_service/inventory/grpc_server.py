import grpc
import logging
from concurrent import futures
from django.db import transaction
from django.db.models import F
from django.utils import timezone
import ticketing_pb2
import ticketing_pb2_grpc
from inventory.models import Event
from inventory.lua_scripts import r, hold_sha, release_sha, sell_sha

logger = logging.getLogger(__name__)


def ensure_redis_initialized(event):
    """Lazy init Redis counters for an event."""
    r.setnx(f"event:{event.id}:available", event.available_tickets)
    r.setnx(f"event:{event.id}:held", event.tickets_held)
    r.setnx(f"event:{event.id}:sold", event.tickets_sold)

class InventoryServicer(ticketing_pb2_grpc.InventoryServiceServicer):
    def HoldTickets(self, request, context):
        try:
            with transaction.atomic():
                event = Event.objects.select_for_update().get(id=request.event_id)
                ensure_redis_initialized(event)

                success = r.evalsha(hold_sha, 0, str(event.id), int(request.quantity), str(request.reservation_id), int(request.ttl_seconds))
                if success != 1:
                    return ticketing_pb2.HoldTicketsResponse(success=False, message="Not enough tickets")

                try:
                    Event.objects.filter(id=event.id).update(
                        tickets_held=F('tickets_held') + request.quantity
                    )
                except Exception as db_exc:  # noqa: BLE001
                    logger.exception("DB update failed after hold; rolling back Redis", exc_info=db_exc)
                    # Roll back Redis hold to keep Redis and DB aligned
                    r.evalsha(release_sha, 0, str(event.id), int(request.quantity), str(request.reservation_id))
                    return ticketing_pb2.HoldTicketsResponse(success=False, message="Hold rolled back due to DB error")

                return ticketing_pb2.HoldTicketsResponse(success=True, message="Tickets held")
        except Event.DoesNotExist:
            context.abort(grpc.StatusCode.NOT_FOUND, "Event not found")

    def ReleaseTickets(self, request, context):
        try:
            with transaction.atomic():
                event = Event.objects.select_for_update().get(id=request.event_id)
                ensure_redis_initialized(event)

                success = r.evalsha(release_sha, 0, str(event.id), int(request.quantity), str(request.reservation_id))
                if success != 1:
                    return ticketing_pb2.ReleaseTicketsResponse(success=False, message="No hold found")

                try:
                    Event.objects.filter(id=event.id).update(
                        tickets_held=F('tickets_held') - request.quantity
                    )
                except Exception as db_exc:  # noqa: BLE001
                    logger.exception("DB update failed after release; restoring Redis hold", exc_info=db_exc)
                    # Recreate the hold so Redis matches DB state
                    r.evalsha(hold_sha, 0, str(event.id), int(request.quantity), str(request.reservation_id), 600)
                    return ticketing_pb2.ReleaseTicketsResponse(success=False, message="Release rolled back due to DB error")

                return ticketing_pb2.ReleaseTicketsResponse(success=True, message="Tickets released")
        except Event.DoesNotExist:
            context.abort(grpc.StatusCode.NOT_FOUND, "Event not found")

    def SellTickets(self, request, context):
        try:
            with transaction.atomic():
                event = Event.objects.select_for_update().get(id=request.event_id)
                ensure_redis_initialized(event)

                success = r.evalsha(sell_sha, 0, str(event.id), int(request.quantity), str(request.reservation_id))
                if success != 1:
                    return ticketing_pb2.SellTicketsResponse(success=False, message="No hold found or insufficient")

                try:
                    Event.objects.filter(id=event.id).update(
                        tickets_held=F('tickets_held') - request.quantity,
                        tickets_sold=F('tickets_sold') + request.quantity,
                    )
                except Exception as db_exc:  # noqa: BLE001
                    logger.exception("DB update failed after sell; restoring Redis hold", exc_info=db_exc)
                    # Recreate the hold so Redis matches DB state
                    r.evalsha(hold_sha, 0, str(event.id), int(request.quantity), str(request.reservation_id), 600)
                    return ticketing_pb2.SellTicketsResponse(success=False, message="Sell rolled back due to DB error")

                return ticketing_pb2.SellTicketsResponse(success=True, message="Tickets sold")
        except Event.DoesNotExist:
            context.abort(grpc.StatusCode.NOT_FOUND, "Event not found")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    ticketing_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryServicer(), server)
    bound_port = server.add_insecure_port('0.0.0.0:50052')
    if bound_port == 0:
        raise RuntimeError("Inventory gRPC failed to bind to port 50052. Is another process using it?")
    server.start()
    print(f"Inventory gRPC server running on port {bound_port}")
    server.wait_for_termination()