from django.db import models
from catalog.models import Product

class Order(models.Model):
    user_id = models.IntegerField()
    email = models.EmailField()
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pedido {self.id} - Usuario {self.user_id}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

class OutboxEvent(models.Model):
    """Almacena el evento dentro de PostgreSQL de forma atómica para el broker"""
    event_type = models.CharField(max_length=100, default='pedido.creado')
    payload = models.JSONField()
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Evento {self.id} - {self.event_type} - Procesado: {self.processed}"