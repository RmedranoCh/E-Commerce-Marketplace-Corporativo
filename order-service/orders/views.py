from decimal import Decimal
from django.db import transaction
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from catalog.models import Product
from .models import Order, OrderItem, OutboxEvent

class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user_id = request.user.id
        email = request.data.get('email')
        items_data = request.data.get('items', [])
        
        if not email or not items_data:
            return Response({"error": "Faltan datos requeridos"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            items_data = sorted(items_data, key=lambda x: int(x['product_id']))
            
            with transaction.atomic():
                order = Order.objects.create(user_id=user_id, email=email)
                total_order = Decimal('0.00')
                items_names = []
                
                for item in items_data:
                    product = Product.objects.select_for_update().get(id=int(item['product_id']))
                    quantity = int(item['quantity'])
                    if product.stock < quantity:
                        raise ValueError(f"Stock insuficiente para {product.name}")
                    product.stock -= quantity
                    product.save()
                    if product.is_offer and product.offer_price is not None:
                        precio_final = product.offer_price
                    else:
                        precio_final = product.price
                        
                    total_order += precio_final * quantity
                    OrderItem.objects.create(
                        order=order, product=product, quantity=quantity, price=precio_final
                    )
                    items_names.append(product.name)
                    
                order.total = total_order
                order.save()
                
                event_payload = {
                    "order_id": int(order.id),
                    "email": str(order.email),
                    "total": str(order.total),
                    "items": [
                        {"name": item_obj.product.name, "quantity": item_obj.quantity}
                        for item_obj in order.items.all()
                    ]
                }
                OutboxEvent.objects.create(event_type='pedido.creado', payload=event_payload)
                
            try:
                cache.delete("catalog_products_list")
            except Exception as cache_error:
                print(f"[CATASTROFICO SILENCIOSO] Redis no disponible en red aislada: {cache_error}. Sincronización diferida.")

            return Response({"message": "Pedido creado exitosamente", "order_id": order.id}, status=status.HTTP_201_CREATED)
            
        except Product.DoesNotExist:
            return Response({"error": "Producto no encontrado"}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as general_error:
            print(f"[CHECKOUT CRITICAL ERROR 500]: {str(general_error)}")
            return Response({"error": "Error interno del servidor al procesar la orden"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)