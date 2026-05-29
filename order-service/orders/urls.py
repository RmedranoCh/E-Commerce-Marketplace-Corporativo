from django.urls import path
from .views import CreateOrderView

urlpatterns = [
    path('checkout/', CreateOrderView.as_view(), name='order-checkout'),
]