import threading
from django.core.management import execute_from_command_line
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_service.settings')
django.setup()

from inventory.grpc_server import serve

if __name__ == '__main__':
    grpc_thread = threading.Thread(target=serve, daemon=True)
    grpc_thread.start()
    execute_from_command_line(['run_servers.py', 'runserver', '8003'])