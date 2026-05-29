from rest_framework import serializers
from .models import Product

class ProductSerializer(serializers.ModelSerializer):
    imagen_urls = serializers.SerializerMethodField()
    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'stock', 'images', 'imagen_urls', 'is_offer', 'offer_price']
        
    def get_imagen_urls(self, obj):
        if not obj.images:
            return []
        urls_limpias = []
        for img in obj.images:
            nombre_limpio = img.replace('/app/media/', '').replace('media/', '').replace('/media/', '').lstrip('/')
            urls_limpias.append(f"/media/{nombre_limpio}")
        return urls_limpias