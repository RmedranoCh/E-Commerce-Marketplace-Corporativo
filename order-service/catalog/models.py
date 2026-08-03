import os
from pathlib import Path

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

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


def _ruta_segura_en_media(ruta_relativa):
    """Resuelve la ruta dentro de MEDIA_ROOT, evitando path traversal."""
    media_root = Path(settings.MEDIA_ROOT).resolve()
    destino = (media_root / str(ruta_relativa).lstrip('/')).resolve()
    if not destino.is_relative_to(media_root):
        return None
    return destino


@receiver(post_delete, sender=Product)
def eliminar_imagenes_en_disco(sender, instance, **kwargs):
    if instance.images:
        for ruta_relativa in instance.images:
            ruta_absoluta = _ruta_segura_en_media(ruta_relativa)
            if ruta_absoluta and ruta_absoluta.exists():
                try:
                    ruta_absoluta.unlink()
                except Exception as e:
                    print(f"[AUDITORÍA DISCO] No se pudo borrar el archivo {ruta_absoluta}: {e}")
