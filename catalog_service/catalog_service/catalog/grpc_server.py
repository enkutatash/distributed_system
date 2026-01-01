# catalog/grpc_server.py
import grpc
from concurrent import futures
import ticketing_pb2
import ticketing_pb2_grpc
from catalog.models import Event
from google.protobuf.timestamp_pb2 import Timestamp


class CatalogServicer(ticketing_pb2_grpc.CatalogServiceServicer):
    def GetEvent(self, request, context):
        try:
            event = Event.objects.get(id=request.event_id)
            start_at = Timestamp()
            start_at.FromDatetime(event.start_at)
            created_at = Timestamp()
            created_at.FromDatetime(event.created_at)

            return ticketing_pb2.GetEventResponse(
                id=str(event.id),
                name=event.name,
                start_at=start_at,
                price_cents=event.price_cents,
                total_tickets=event.total_tickets,
                tickets_sold=event.tickets_sold,
                tickets_held=event.tickets_held,
                available_tickets=event.available_tickets,
                metadata=event.metadata or {},
                created_at=created_at,
            )
        except Event.DoesNotExist:
            context.abort(grpc.StatusCode.NOT_FOUND, "Event not found")


def serve_grpc():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    ticketing_pb2_grpc.add_CatalogServiceServicer_to_server(CatalogServicer(), server)
    server.add_insecure_port('0.0.0.0:60001')
    server.start()
    print("gRPC server started on port 60001")
    server.wait_for_termination()