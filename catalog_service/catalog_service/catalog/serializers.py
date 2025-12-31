from rest_framework import serializers
from .models import Event
import os

class EventSerializer(serializers.ModelSerializer):
    available_tickets = serializers.IntegerField(read_only=True)
    image = serializers.ImageField(required=False, allow_null=True, write_only=True)  # Write-only for uploads
    image_url = serializers.SerializerMethodField(read_only=True)  # Returns Cloudinary URL
    global_image_url = serializers.SerializerMethodField(read_only=True)  # Public Cloudinary URL

    class Meta:
        model = Event
        fields = [
            'id',
            'name',
            'start_at',
            'price_cents',
            'total_tickets',
            'tickets_sold',
            'tickets_held',
            'image',
            'image_url',
            'global_image_url',
            'available_tickets',
            'metadata',
            'created_at',
        ]
        read_only_fields = [
            'tickets_sold',
            'tickets_held',
            'created_at',
            'available_tickets',
            'image_url',
            'global_image_url',
        ]

    def get_image_url(self, obj):
        """Return Cloudinary URL for the image"""
        return self.get_global_image_url(obj)

    def get_global_image_url(self, obj):
        """Return public Cloudinary URL if image exists"""
        if obj.image:
            # Get the URL from the storage backend
            url = obj.image.url
            
            # If it's already a full Cloudinary URL (starts with https://res.cloudinary.com), return it
            if url.startswith('https://res.cloudinary.com'):
                return url
            
            # If it's a local URL or relative path, we need to get the Cloudinary URL
            # Check if the storage is Cloudinary storage
            from cloudinary_storage.storage import MediaCloudinaryStorage
            if isinstance(obj.image.storage, MediaCloudinaryStorage):
                # Get cloud name from environment or storage
                cloudinary_url = os.environ.get('CLOUDINARY_URL', '')
                if cloudinary_url:
                    from urllib.parse import urlparse
                    parsed = urlparse(cloudinary_url)
                    cloud_name = parsed.hostname
                else:
                    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', 'dbpcqezob')
                
                # Extract the path from the URL (remove /media/ prefix if present)
                path = url.replace('/media/', '').lstrip('/')
                # Construct full Cloudinary URL
                return f"https://res.cloudinary.com/{cloud_name}/image/upload/{path}"
            
            # Fallback: return the URL as-is
            return url
        return None