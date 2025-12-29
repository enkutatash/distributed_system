import redis
from django.core.management.base import BaseCommand
from django.db import transaction
from inventory.models import Event
from inventory.lua_scripts import r


class Command(BaseCommand):
    help = "Sync Redis counters with DB for inventory events"

    def add_arguments(self, parser):
        parser.add_argument(
            "--from-redis",
            action="store_true",
            help="Use Redis as source of truth and write DB counters from Redis values",
        )

    def handle(self, *args, **options):
        use_redis_as_source = options.get("from_redis", False)
        synced = 0
        with transaction.atomic():
            for event in Event.objects.select_for_update().all():
                held_key = f"event:{event.id}:held"
                sold_key = f"event:{event.id}:sold"
                available_key = f"event:{event.id}:available"

                # Read Redis values, fall back to DB if missing
                r_held = int(r.get(held_key) or event.tickets_held)
                r_sold = int(r.get(sold_key) or event.tickets_sold)
                r_available = int(r.get(available_key) or max(event.total_tickets - r_sold - r_held, 0))

                if use_redis_as_source:
                    # Update DB from Redis
                    event.tickets_held = r_held
                    event.tickets_sold = r_sold
                    event.save(update_fields=["tickets_held", "tickets_sold"])
                    # Recompute available and push back to Redis to keep both aligned
                    recomputed_available = max(event.total_tickets - event.tickets_sold - event.tickets_held, 0)
                    r.mset({held_key: event.tickets_held, sold_key: event.tickets_sold, available_key: recomputed_available})
                else:
                    # DB is source of truth; push to Redis
                    recomputed_available = max(event.total_tickets - event.tickets_sold - event.tickets_held, 0)
                    r.mset({held_key: event.tickets_held, sold_key: event.tickets_sold, available_key: recomputed_available})

                self.stdout.write(
                    f"Synced event {event.id}: held={r_held}/{event.tickets_held} sold={r_sold}/{event.tickets_sold} available={r_available}->{max(event.total_tickets - event.tickets_sold - event.tickets_held, 0)}"
                )
                synced += 1

        self.stdout.write(self.style.SUCCESS(f"Sync complete for {synced} events (source={'redis' if use_redis_as_source else 'db'})"))
