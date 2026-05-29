import os
import uuid
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import BasePermission
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.core.files.storage import default_storage
from django.core.cache import cache
from django.conf import settings
from .models import Product
from .serializers import ProductSerializer

class IsProveedor(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'token_role', None) == 'proveedor'
        )

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
            is_offer_raw = request.data.get('is_offer', 'false')
            is_offer = str(is_offer_raw).lower() in ['true', '1', 'on']
            offer_price = request.data.get('offer_price', None)
            if offer_price == '' or offer_price == 'null':
                offer_price = None

            if not name or not price or not stock:
                return Response({"error": "Faltan parámetros obligatorios (name, price, stock)"}, status=status.HTTP_400_BAD_REQUEST)

            product = Product.objects.create(
                name=str(name).strip(), 
                price=price, 
                stock=int(stock), 
                description=description,
                is_offer=is_offer,
                offer_price=offer_price if is_offer else None
            )
            
            saved_paths = []
            archivos_multimedia = request.FILES.getlist('img_archivos')
            if archivos_multimedia:
                for file_obj in archivos_multimedia:
                    if file_obj and getattr(file_obj, 'name', '') != '':
                        ext = os.path.splitext(str(file_obj.name))[1].lower()
                        filename = f"products/prod_{product.id}_img_{uuid.uuid4().hex[:6]}{ext}"
                        path = default_storage.save(filename, file_obj)
                        saved_paths.append(path)
            else:
                for file_key, file_obj in request.FILES.items():
                    if file_key.startswith('img') and file_obj:
                        ext = os.path.splitext(str(file_obj.name))[1].lower()
                        filename = f"products/prod_{product.id}_img_{uuid.uuid4().hex[:6]}{ext}"
                        path = default_storage.save(filename, file_obj)
                        saved_paths.append(path)
                        
            product.images = saved_paths
            product.save()
            try:
                cache.delete("catalog_products_list")
            except Exception:
                pass
            serializer = self.get_serializer(product)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            print(f"=========================================================")
            print(f"🚨 [CRITICAL EXCEPTION IN DJANGO CREATE]: {str(e)}")
            return Response({"error": f"Fallo interno en el microservicio: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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