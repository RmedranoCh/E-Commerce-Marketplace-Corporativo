from rest_framework import serializers
from .models import Product

MAX_DESCRIPCION = 250


class ProductSerializer(serializers.ModelSerializer):
    imagen_urls = serializers.SerializerMethodField()
    images = serializers.JSONField(read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'stock', 'images', 'imagen_urls', 'is_offer', 'offer_price']

    def validate_description(self, value):
        if value is not None and len(value) > MAX_DESCRIPCION:
            raise serializers.ValidationError(f"La descripción no puede superar los {MAX_DESCRIPCION} caracteres.")
        return value

    def validate_price(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("El precio debe ser mayor que cero.")
        return value

    def validate_stock(self, value):
        if value is None or value < 0:
            raise serializers.ValidationError("El stock no puede ser negativo.")
        return value

    def validate(self, attrs):
        if attrs.get('is_offer'):
            offer_price = attrs.get('offer_price')
            price = attrs.get('price', getattr(self.instance, 'price', None))
            if offer_price is None:
                raise serializers.ValidationError({"offer_price": "El precio de oferta es obligatorio."})
            if offer_price <= 0:
                raise serializers.ValidationError({"offer_price": "El precio de oferta debe ser mayor que cero."})
            if price is not None and offer_price >= price:
                raise serializers.ValidationError({"offer_price": "El precio de oferta debe ser menor que el precio base."})
        return attrs

    def get_imagen_urls(self, obj):
        if not obj.images:
            return []
        urls_limpias = []
        for img in obj.images:
            nombre_limpio = str(img).replace('/app/media/', '').replace('media/', '').replace('/media/', '').lstrip('/')
            urls_limpias.append(f"/media/{nombre_limpio}")
        return urls_limpias
