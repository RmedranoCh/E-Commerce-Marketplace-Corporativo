import os
import uuid
from decimal import Decimal, InvalidOperation
from io import BytesIO

from PIL import Image
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db.models import F
from rest_framework import generics, status
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from .models import Product
from .serializers import ProductSerializer

MAX_IMAGENES = 7
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
EXTENSIONES_PERMITIDAS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


class IsProveedor(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'token_role', None) == 'proveedor'
        )


def validar_archivo_imagen(file_obj):
    ext = os.path.splitext(str(file_obj.name))[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        raise ValidationError("Formato de imagen no permitido.")
    if file_obj.size and file_obj.size > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError("La imagen supera el tamaño máximo de 5MB.")
    try:
        file_obj.seek(0)
        Image.open(BytesIO(file_obj.read())).verify()
        file_obj.seek(0)
    except Exception:
        raise ValidationError("El archivo no es una imagen válida.")


class ProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsProveedor]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method == 'GET':
            return []
        return [IsProveedor()]

    def list(self, request, *args, **kwargs):
        cache_key = "catalog_products_list"
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data, status=status.HTTP_200_OK)
        queryset = Product.objects.all()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        cache.set(cache_key, data, timeout=300)
        return Response(data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        try:
            name = request.data.get('name')
            price = request.data.get('price')
            stock = request.data.get('stock')
            description = request.data.get('description', 'Inyectado con archivos multimedia')
            is_offer = str(request.data.get('is_offer', 'false')).lower() in ['true', '1', 'on']
            offer_price = request.data.get('offer_price', None)
            if offer_price in ('', 'null', None):
                offer_price = None

            if not name or price is None or stock is None:
                return Response({"error": "Faltan parámetros obligatorios (name, price, stock)"}, status=status.HTTP_400_BAD_REQUEST)

            nombre_limpio = str(name).strip()
            if not nombre_limpio:
                return Response({"error": "El nombre del producto no puede estar vacío."}, status=status.HTTP_400_BAD_REQUEST)
            if len(nombre_limpio) > 255:
                return Response({"error": "El nombre del producto no puede superar 255 caracteres."}, status=status.HTTP_400_BAD_REQUEST)

            try:
                price_dec = Decimal(str(price))
                stock_int = int(stock)
            except (TypeError, ValueError, InvalidOperation):
                return Response({"error": "Precio o stock inválidos."}, status=status.HTTP_400_BAD_REQUEST)

            if price_dec <= 0:
                return Response({"error": "El precio debe ser mayor que cero."}, status=status.HTTP_400_BAD_REQUEST)
            if stock_int < 0:
                return Response({"error": "El stock no puede ser negativo."}, status=status.HTTP_400_BAD_REQUEST)
            if description and len(str(description)) > 250:
                return Response({"error": "La descripción no puede superar 250 caracteres."}, status=status.HTTP_400_BAD_REQUEST)

            offer_dec = None
            if is_offer:
                if offer_price is None:
                    return Response({"error": "El precio de oferta es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
                try:
                    offer_dec = Decimal(str(offer_price))
                except (TypeError, ValueError, InvalidOperation):
                    return Response({"error": "Precio de oferta inválido."}, status=status.HTTP_400_BAD_REQUEST)
                if offer_dec <= 0:
                    return Response({"error": "El precio de oferta debe ser mayor que cero."}, status=status.HTTP_400_BAD_REQUEST)
                if offer_dec >= price_dec:
                    return Response({"error": "El precio de oferta debe ser menor que el precio base."}, status=status.HTTP_400_BAD_REQUEST)

            product = Product.objects.create(
                name=nombre_limpio,
                price=price_dec,
                stock=stock_int,
                description=description,
                is_offer=is_offer,
                offer_price=offer_dec if is_offer else None,
            )

            archivos_multimedia = request.FILES.getlist('img_archivos')
            if len(archivos_multimedia) > MAX_IMAGENES:
                product.delete()
                return Response({"error": f"Máximo {MAX_IMAGENES} imágenes por producto."}, status=status.HTTP_400_BAD_REQUEST)

            saved_paths = []
            for file_obj in archivos_multimedia:
                if file_obj and getattr(file_obj, 'name', '') != '':
                    validar_archivo_imagen(file_obj)
                    ext = os.path.splitext(str(file_obj.name))[1].lower()
                    filename = f"products/prod_{product.id}_img_{uuid.uuid4().hex[:6]}{ext}"
                    path = default_storage.save(filename, file_obj)
                    saved_paths.append(path)

            if saved_paths:
                product.images = saved_paths
                product.save()

            try:
                cache.delete("catalog_products_list")
            except Exception:
                pass
            serializer = self.get_serializer(product)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"[CRITICAL EXCEPTION IN DJANGO CREATE]: {str(e)}")
            return Response({"error": "Fallo interno en el microservicio."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    lookup_field = 'id'

    def get_permissions(self):
        if self.request.method in ['GET']:
            return []
        return [IsProveedor()]

    def perform_update(self, serializer):
        serializer.save()
        try:
            cache.delete("catalog_products_list")
        except Exception:
            pass

    def perform_destroy(self, instance):
        instance.delete()
        try:
            cache.delete("catalog_products_list")
        except Exception:
            pass


class ProductRestockView(generics.GenericAPIView):
    permission_classes = [IsProveedor]

    def post(self, request, id):
        try:
            quantity = int(request.data.get('quantity', 0))
        except (TypeError, ValueError):
            return Response({"error": "Cantidad inválida."}, status=status.HTTP_400_BAD_REQUEST)
        if quantity <= 0:
            return Response({"error": "La cantidad debe ser mayor que cero."}, status=status.HTTP_400_BAD_REQUEST)
        if quantity > 10000:
            return Response({"error": "La cantidad supera el límite permitido."}, status=status.HTTP_400_BAD_REQUEST)

        updated = Product.objects.filter(id=id).update(stock=F('stock') + quantity)
        if updated == 0:
            return Response({"error": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        try:
            cache.delete("catalog_products_list")
        except Exception:
            pass
        product = Product.objects.get(id=id)
        return Response(ProductSerializer(product).data, status=status.HTTP_200_OK)
