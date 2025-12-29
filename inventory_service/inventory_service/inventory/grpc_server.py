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
                    # Collect debug info and log inline so it appears in default console output
                    hold_key = f"hold:{str(request.reservation_id)}"
                    try:
                        held_quantity = int(r.get(hold_key) or 0)
                        ttl = int(r.ttl(hold_key) or -1)
                    except Exception:
                        held_quantity = -1
                        ttl = -1
                    try:
                        redis_held = int(r.get(f"event:{str(event.id)}:held") or 0)
                        redis_sold = int(r.get(f"event:{str(event.id)}:sold") or 0)
                        redis_available = int(r.get(f"event:{str(event.id)}:available") or 0)
                    except Exception:
                        redis_held = redis_sold = redis_available = -1

                    # Fallback repair: if hold key missing but counters show held >= requested, rebuild the hold and retry once
                    rebuilt = False
                    if held_quantity <= 0 and redis_held >= int(request.quantity):
                        r.setex(hold_key, 300, int(request.quantity))
                        rebuilt = True
                        success_retry = r.evalsha(sell_sha, 0, str(event.id), int(request.quantity), str(request.reservation_id))
                        if success_retry == 1:
                            logger.warning(
                                "SellTickets repaired missing hold and succeeded",
                                extra={
                                    "event_id": str(event.id),
                                    "reservation_id": str(request.reservation_id),
                                    "requested_qty": int(request.quantity),
                                    "held_qty": held_quantity,
                                    "redis_held": redis_held,
                                },
                            )
                            return ticketing_pb2.SellTicketsResponse(success=True, message="Repaired hold and sold")

                    logger.warning(
                        (
                            "SellTickets failed: event=%s res=%s req_qty=%d held_qty=%d ttl=%d "
                            "redis{held=%d sold=%d available=%d} rebuilt=%s"
                        ),
                        str(event.id),
                        str(request.reservation_id),
                        int(request.quantity),
                        held_quantity,
                        ttl,
                        redis_held,
                        redis_sold,
                        redis_available,
                        rebuilt,
                    )
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