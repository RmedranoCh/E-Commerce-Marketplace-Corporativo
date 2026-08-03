from django.urls import path
from .views import ProductListCreateView, ProductRetrieveUpdateDestroyView, ProductRestockView

urlpatterns = [
    path('products/', ProductListCreateView.as_view(), name='product-list-create'),
    path('products/<int:id>/', ProductRetrieveUpdateDestroyView.as_view(), name='product-detail'),
    path('products/<int:id>/restock/', ProductRestockView.as_view(), name='product-restock'),
]
