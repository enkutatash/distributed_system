# run_servers.py
import threading
import os
import django

# Ensure the Django settings are set before importing any app modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'catalog_service.settings')
django.setup()

# Import gRPC server after Django is configured so model imports are safe
from catalog.grpc_server import serve_grpc

# Start gRPC in background thread
grpc_thread = threading.Thread(target=serve_grpc, daemon=True)
grpc_thread.start()

# Start Django HTTP server
from django.core.management import execute_from_command_line
import sys
execute_from_command_line(sys.argv)