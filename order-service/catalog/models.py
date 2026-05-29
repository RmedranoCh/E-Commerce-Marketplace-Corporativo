import os
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.conf import settings

class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(decimal_places=2, max_digits=10)
    stock = models.IntegerField(default=0)
    images = models.JSONField(default=list, blank=True)
    is_offer = models.BooleanField(default=False)
    offer_price = models.DecimalField(decimal_places=2, max_digits=10, blank=True, null=True)
    def __str__(self):
        return self.name

@receiver(post_delete, sender=Product)
def eliminar_imagenes_en_disco(sender, instance, **kwargs):
    if instance.images:
        for ruta_relativa in instance.images:
            ruta_absoluta = os.path.join(settings.BASE_DIR, ruta_relativa.lstrip('/'))
            if os.path.exists(ruta_absoluta):
                try:
                    os.remove(ruta_absoluta)
                except Exception as e:
                    print(f"[AUDITORÍA DISCO] No se pudo borrar el archivo {ruta_absoluta}: {e}")