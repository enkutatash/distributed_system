import threading
from django.core.management import execute_from_command_line
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_service.settings')
django.setup()

from inventory.grpc_server import serve

if __name__ == '__main__':
    grpc_thread = threading.Thread(target=serve, daemon=True)
    grpc_thread.start()
    # Pass through CLI args so the HTTP server uses the requested host:port
    # Example: python run_servers.py runserver 0.0.0.0:8004
    execute_from_command_line(sys.argv)