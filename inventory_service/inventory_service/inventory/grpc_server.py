import grpc
from concurrent import futures
from django.utils import timezone
import ticketing_pb2
import ticketing_pb2_grpc
from inventory.models import Event
from inventory.lua_scripts import r, hold_sha, release_sha, sell_sha

class InventoryServicer(ticketing_pb2_grpc.InventoryServiceServicer):
    def HoldTickets(self, request, context):
        try:
            event = Event.objects.get(id=request.event_id)
            # Initialize Redis keys if first time
            r.setnx(f"event:{event.id}:available", event.available_tickets)
            r.setnx(f"event:{event.id}:held", event.tickets_held)
            r.setnx(f"event:{event.id}:sold", event.tickets_sold)

            success = r.evalsha(hold_sha, 0, event.id, request.quantity, request.reservation_id, request.ttl_seconds)
            if success == 1:
                event.tickets_held += request.quantity
                event.save(update_fields=['tickets_held'])
                return ticketing_pb2.HoldTicketsResponse(success=True, message="Tickets held")
            else:
                return ticketing_pb2.HoldTicketsResponse(success=False, message="Not enough tickets")
        except Event.DoesNotExist:
            context.abort(grpc.StatusCode.NOT_FOUND, "Event not found")

    def ReleaseTickets(self, request, context):
        try:
            event = Event.objects.get(id=request.event_id)
            success = r.evalsha(release_sha, 0, event.id, request.quantity, request.reservation_id)
            if success == 1:
                event.tickets_held -= request.quantity
                event.save(update_fields=['tickets_held'])
                return ticketing_pb2.ReleaseTicketsResponse(success=True, message="Tickets released")
            else:
                return ticketing_pb2.ReleaseTicketsResponse(success=False, message="No hold found")
        except Event.DoesNotExist:
            context.abort(grpc.StatusCode.NOT_FOUND, "Event not found")

    def SellTickets(self, request, context):
        try:
            event = Event.objects.get(id=request.event_id)
            success = r.evalsha(sell_sha, 0, event.id, request.quantity, request.reservation_id)
            if success == 1:
                event.tickets_held -= request.quantity
                event.tickets_sold += request.quantity
                event.save(update_fields=['tickets_held', 'tickets_sold'])
                return ticketing_pb2.SellTicketsResponse(success=True, message="Tickets sold")
            else:
                return ticketing_pb2.SellTicketsResponse(success=False, message="No hold found or insufficient")
        except Event.DoesNotExist:
            context.abort(grpc.StatusCode.NOT_FOUND, "Event not found")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    ticketing_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryServicer(), server)
    server.add_insecure_port('[::]:50052')
    server.start()
    print("Inventory gRPC server running on port 50052")
    server.wait_for_termination()