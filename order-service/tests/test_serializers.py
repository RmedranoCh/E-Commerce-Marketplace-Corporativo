"""Tests de demostración del order-service: validaciones del catálogo.

No requieren PostgreSQL: se validan los serializadores y el saneamiento de
URLs de imágenes con instancias sin persistir.
"""

from decimal import Decimal

from catalog.models import Product
from catalog.serializers import ProductSerializer


def test_serializer_acepta_datos_validos():
    data = {
        'name': 'Laptop Corporativa',
        'price': '1999.99',
        'stock': 5,
        'description': 'Equipo de alta gama',
        'is_offer': False,
    }
    s = ProductSerializer(data=data)
    assert s.is_valid()
    assert s.validated_data['price'] == Decimal('1999.99')


def test_precio_debe_ser_mayor_que_cero():
    s = ProductSerializer(data={'name': 'X', 'price': '0', 'stock': 1})
    assert not s.is_valid()
    assert 'price' in s.errors


def test_precio_negativo_rechazado():
    s = ProductSerializer(data={'name': 'X', 'price': '-5.00', 'stock': 1})
    assert not s.is_valid()
    assert 'price' in s.errors


def test_stock_no_puede_ser_negativo():
    s = ProductSerializer(data={'name': 'X', 'price': '10.00', 'stock': -3})
    assert not s.is_valid()
    assert 'stock' in s.errors


def test_descripcion_no_supera_250_caracteres():
    s = ProductSerializer(data={
        'name': 'X',
        'price': '10.00',
        'stock': 1,
        'description': 'a' * 251,
    })
    assert not s.is_valid()
    assert 'description' in s.errors


def test_oferta_sin_precio_de_oferta_rechazada():
    s = ProductSerializer(data={
        'name': 'X',
        'price': '100.00',
        'stock': 1,
        'is_offer': True,
    })
    assert not s.is_valid()
    assert 'offer_price' in s.errors


def test_precio_de_oferta_debe_ser_menor_al_base():
    s = ProductSerializer(data={
        'name': 'X',
        'price': '100.00',
        'stock': 1,
        'is_offer': True,
        'offer_price': '100.00',
    })
    assert not s.is_valid()
    assert 'offer_price' in s.errors


def test_oferta_valida():
    s = ProductSerializer(data={
        'name': 'X',
        'price': '100.00',
        'stock': 1,
        'is_offer': True,
        'offer_price': '89.99',
    })
    assert s.is_valid()


def test_urls_de_imagenes_se_liman_para_el_navegador():
    producto = Product(images=[
        '/app/media/products/foto1.jpg',
        'media/foto2.png',
        '/media/foto3.webp',
    ])
    data = ProductSerializer(producto).data
    assert data['imagen_urls'] == [
        '/media/products/foto1.jpg',
        '/media/foto2.png',
        '/media/foto3.webp',
    ]


def test_producto_sin_imagenes_devuelve_lista_vacia():
    producto = Product(images=[])
    assert ProductSerializer(producto).data['imagen_urls'] == []
