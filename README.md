# E-Commerce Marketplace Corporativo

Marketplace de comercio electrónico con arquitectura de microservicios. Compradores y proveedores funcionan en un mismo sistema donde cada pieza hace su trabajo de forma independiente pero coordinada: los compradores navegan productos, arman su carrito y compran en tiempo real; los proveedores gestionan su inventario, publican productos y controlan stock.

---

## Arquitectura del sistema

El sistema se organiza como microservicios que se comunican entre sí a través de redes internas. Un gateway (Nginx) es el único punto de entrada y dirige cada petición al servicio correcto.

```
[ Navegador del Usuario ]
          |
          ▼ (Puerto 80)
  [ Nginx Gateway ]
          |
         ┌┴────────────────────────┐
         ▼ /                     ▼ /api/
  [ web-frontend ]        [ auth-service ]
  (FastAPI / BFF)         (Flask / SQLite)
         |
         ▼ /api/orders/
  [ order-service ] ──► [ Outbox Event ] ──► [ outbox-worker ]
 (Django REST / Postgres)                    |
         ▲                                   ▼ (AMQP)
         │                          [ RabbitMQ Broker ]
         └────────── [ Redis Cache ]         |
                                             ▼
                                  [ notification-service ]
```

### Componentes

| Componente | Qué hace |
|------------|----------|
| **Nginx Gateway** | Único punto de entrada. Dirige el tráfico por URL y sirve imágenes y archivos multimedia. |
| **web-frontend (BFF)** | FastAPI que renderiza las páginas (Jinja2) y orquesta las llamadas a los demás servicios. Maneja el login con JWT. |
| **auth-service** | Flask + SQLite aislada. Registro, inicio de sesión y verificación con JWT firmado en RS256. Roles: comprador y proveedor. |
| **order-service** | Django 5 + DRF + PostgreSQL. Catálogo, inventario y órdenes. Usa bloqueos de fila (`select_for_update`) y el patrón Outbox. |
| **outbox-worker** | Revisa la tabla Outbox, publica los eventos de pedidos en RabbitMQ y los marca como procesados. |
| **RabbitMQ** | Broker de mensajería. Distribuye los eventos de pedidos por la cola `pedido.creado`. |
| **notification-service** | Consume los mensajes y simula el envío de correos de confirmación (listo para conectar un servicio real). |
| **Redis** | Caché del catálogo y control de idempotencia de notificaciones. |

---

## Características

- **Compra en tiempo real**: si un producto se agota, desaparece del catálogo sin recargar la página.
- **Carrito persistente** en el navegador (localStorage) por 7 días.
- **Panel de proveedor** (Proveedor) con estética cyberpunk: inventario que se actualiza solo, alta de productos con fotos, reabastecimiento y eliminatoria.
- **Validación en 3 capas**: navegador, BFF y core (por ejemplo, la descripción de un producto tiene un límite de 250 caracteres aplicado en cada nivel).
- **Autenticación JWT con RSA (RS256)**: auth-service firma, los demás servicios verifican con la llave pública. Sin secretos compartidos.
- **Redes Docker aisladas**: `public-gateway`, `backend-mesh` y `data-isolated` (bases de datos sin acceso externo). Todos los servicios corren como usuario no-root.
- **Ningún pedido se pierde**: patrón Outbox + RabbitMQ garantizan la notificación aunque un servicio se caiga.

---

## Tecnologías

| Tipo | Tecnologías |
|------|------------|
| **Backend** | Django 5.0, FastAPI 0.110, Flask 3.0, Django REST Framework 3.14 |
| **Bases de datos** | PostgreSQL 15, Redis 7, SQLite |
| **Mensajería** | RabbitMQ 3 (AMQP), Pika 1.3 |
| **Servidores** | Docker Compose, Gunicorn, Uvicorn, Nginx |
| **Frontend** | HTML5, CSS3 (Flexbox/Grid), JavaScript nativo, Google Fonts (Inter, Orbitron, Share Tech Mono) |

---

## Estructura del proyecto

```
ecommerce-marketplace/
├── auth-service/          # Servicio de autenticación (Flask + SQLite)
├── gateway/               # Proxy inverso Nginx
├── notification-service/  # Servicio de notificaciones (FastAPI + RabbitMQ)
├── order-service/         # Core del negocio (Django REST + PostgreSQL)
├── web-frontend/          # BFF (FastAPI + Jinja2)
├── postgres-init/         # Script de inicialización de PostgreSQL
├── docker-compose.yml     # Orquestación completa
├── .env.example           # Plantilla de variables de entorno (sin secretos)
└── .gitignore
```

---

## Puesta en marcha

### Requisitos

- **Docker Desktop** (versión 20.10 o superior).
- **Docker Compose** (versión 2.0 o superior).

### Pasos

```bash
# 1. Clona el repositorio
git clone https://github.com/RmedranoCh/E-Commerce-Marketplace-Corporativo.git
cd E-Commerce-Marketplace-Corporativo

# 2. Levanta todo el sistema
docker compose up --build -d
```

El sistema arranca todos los servicios en orden: PostgreSQL se inicializa con su usuario y base de datos, Django ejecuta las migraciones y todo queda listo para usar.

> Los valores sensibles se definen en el `.env` (ignorado por Git). Consulta `.env.example` para la lista completa de variables.

### Puertos de acceso

| URL | Qué es |
|-----|----------|
| http://localhost/comprador | Catálogo de comprador (Comprador) |
| http://localhost/proveedor | Panel de proveedor (Proveedor) |
| http://localhost/admin | Administración Django de órdenes |
| http://localhost:15672 | Consola de RabbitMQ (guest / guest) |

---

## Flujo de una compra

1. El comprador navega el catálogo y agrega productos al carrito.
2. Al confirmar, `order-service` valida el stock (bloquea la fila del producto para evitar condiciones de carrera), descuenta inventario y crea la orden.
3. En la misma transacción se crea un evento en la tabla **Outbox**.
4. `outbox-worker` detecta el evento, lo publica en **RabbitMQ** y lo marca como procesado.
5. `notification-service` consume el mensaje, verifica en Redis que no esté duplicado y simula el correo de confirmación.
6. El comprador ve el resultado en pantalla sin recargar.

---

## Tests

Cada microservicio incluye tests unitarios con **pytest** para sus flujos críticos (autenticación, validaciones de catálogo, rutas del BFF y notificaciones). Corren **sin Docker ni servicios externos**: usan bases SQLite temporales y simulan los servicios upstream.

```bash
# 1. Instala las dependencias de desarrollo (una sola vez)
pip install -r requirements-dev.txt

# 2. Ejecuta los tests de cada microservicio
cd auth-service && python -m pytest tests -v
cd order-service && python -m pytest tests -v
cd web-frontend && python -m pytest tests -v
cd notification-service && python -m pytest tests -v
```

> `requirements-dev.txt` fija versiones mínimas compatibles con Python 3.13. Para reproducir el entorno exacto de producción se usan los `requirements.txt` de cada servicio (imágenes Docker).

---

## Licencia

Proyecto desarrollado con fines académicos y como demostración de arquitectura de microservicios para comercio electrónico. Desarrollado y mantenido por **Rodrigo Medrano** © 2026.

---

¿Lo prefieres en inglés? → [README.en.md](README.en.md)