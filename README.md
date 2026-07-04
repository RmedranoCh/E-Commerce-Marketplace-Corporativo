# AliMarket & TechMarket — E-Commerce Marketplace Corporativo

**Creado por Rodrigo Medrano © 2026**

AliMarket (para compradores) y TechMarket (para proveedores) forman un marketplace de comercio electrónico pensado para ser robusto, escalable y seguro. Está construido con una arquitectura de microservicios, donde cada pieza hace su trabajo de forma independiente pero coordinada, como un sistema bien engrasado.

La idea es simple pero poderosa: los compradores pueden navegar productos, ver ofertas y comprar; los proveedores pueden gestionar su inventario, añadir productos y controlar stock. Todo esto funciona en tiempo real, con actualizaciones automáticas y sin necesidad de recargar la página.

---

## ¿Cómo está organizado el sistema?

Imagina que el sistema es una ciudad con varios edificios especializados. Cada edificio (microservicio) tiene una función concreta, y se comunican entre sí a través de redes internas. No todo el mundo puede entrar a cualquier edificio — hay un guardia de seguridad (Nginx) en la entrada principal que dirige a cada persona al lugar correcto.

```
                  [ Navegador del Usuario ]
                            |
                            ▼ (Puerto 80)
                    [ Nginx Gateway ]
                            |
           ┌────────────────┴────────────────┐
           ▼ /                               ▼ /api/
    [ web-frontend ]                  [ auth-service ]
    (FastAPI / BFF)                   (Flask / SQLite)
           |
           ▼ /api/orders/
    [ order-service ] ───► [ Outbox Event ] ───► [ outbox-worker ]
 (Django REST / Postgres)                             |
           ▲                                          ▼ (AMQP)
           │                                    [ RabbitMQ Broker ]
           └─────────────── [ Redis Cache ]           |
                                                      ▼
                                           [ notification-service ]
```

### ¿Qué hace cada componente?

#### 🚪 Nginx Gateway — El portero digital
Es el único punto de entrada que existe hacia el sistema. Cuando alguien visita la página, Nginx recibe la petición y decide a qué servicio enviarla según la URL. También sirve directamente las imágenes y archivos multimedia (como fotos de productos) para que todo cargue rápido. Está configurado con compresión gzip, buffers optimizados y límites de tamaño para evitar abusos.

#### 🌐 web-frontend (BFF) — La fachada amigable
Este servicio está hecho con **FastAPI** y actúa como el "traductor" entre el navegador y el resto del sistema. Renderiza las páginas HTML que ves en pantalla usando Jinja2, y se encarga de orquestar las llamadas a los otros servicios para darte todo lo que necesitas en una sola respuesta. Aquí es donde se genera tanto la interfaz de comprador (TechMarket) como la de proveedor (Cybercore). También maneja las cookies de sesión con tokens JWT.

#### 🔐 auth-service — El guardia de identidad
Construido con **Flask** y una base de datos **SQLite** aislada, se encarga de todo lo relacionado con usuarios: registrarse, iniciar sesión y verificar quién eres. Usa **JWT con firma asimétrica RS256** (un par de llaves pública/privada) para generar tokens que caducan a las 2 horas. Los usuarios pueden ser de dos tipos: **comprador** (quien compra) o **proveedor** (quien vende y gestiona productos).

#### 📦 order-service — El corazón del negocio
Hecho con **Django 5.0 + Django REST Framework** y conectado a **PostgreSQL**, este servicio maneja el catálogo de productos, los inventarios y las órdenes de compra. Usa bloqueos a nivel de fila (`select_for_update`) para evitar que dos personas compren el último producto al mismo tiempo (condiciones de carrera). También guarda los eventos de pedidos en una tabla especial llamada **Outbox** para asegurar que ningún pedido se pierda.

#### 📤 outbox-worker — El cartero confiable
Es un worker en Python que corre en un contenedor separado. Su trabajo es sencillo pero crucial: revisa constantemente la tabla Outbox en PostgreSQL, toma los eventos de pedidos nuevos (uno por uno, con bloqueos para no pisarse), los publica en **RabbitMQ** y los marca como procesados. Así nos aseguramos de que cada pedido genera su notificación, incluso si el sistema se cae a medio camino.

#### 🐰 RabbitMQ — La central de mensajes
Es el sistema de mensajería que recibe los eventos de pedidos y los distribuye a los servicios que necesitan saber de ellos. Todo pasa por una cola llamada `pedido.creado` con mensajes persistentes (no se pierden aunque RabbitMQ se reinicie).

#### 🔔 notification-service — El notificador
Escrito en **FastAPI**, este servicio consume los mensajes de RabbitMQ y simula el envío de correos electrónicos de confirmación de pedido (en esta versión solo imprime en consola, pero está listo para conectarse a un servicio de email real). Usa **Redis** para asegurarse de que cada pedido se notifique una sola vez (exactamente una vez), incluso si el mensaje llega duplicado.

#### ⚡ Redis Cache — La memoria ultrarrápida
Redis actúa como caché del catálogo de productos. Cuando alguien visita la tienda, los productos se cargan desde Redis en lugar de ir a PostgreSQL, lo que hace que todo sea mucho más rápido. La caché se actualiza cada 5 minutos y se invalida automáticamente cuando un proveedor añade o modifica un producto.

---

## Tecnologías utilizadas

| Tipo | Tecnologías |
|------|------------|
| **Backend** | Django 5.0, FastAPI 0.110, Flask 3.0, Django REST Framework 3.14 |
| **Bases de datos** | PostgreSQL 15, Redis 7, SQLite |
| **Mensajería** | RabbitMQ 3 (AMQP), Pika 1.3 |
| **Servidores** | Docker, Docker Compose, Gunicorn, Uvicorn, Nginx |
| **Frontend** | HTML5, CSS3 (Flexbox/Grid), JavaScript nativo, Google Fonts (Inter, Orbitron, Share Tech Mono) |

---

## Seguridad: cómo protegemos los datos

### 🛡️ Cortafuegos en cascada (validación de 3 capas)

Un ejemplo concreto: la descripción de un producto tiene un límite de **250 caracteres**. Este límite se aplica en tres niveles distintos, por si alguien intenta saltárselo:

1. **Navegador (HTML5/JS):** El campo tiene `maxlength="250"` y un contador en tiempo real que avisa visualmente cuando te estás acercando al límite.
2. **BFF (FastAPI):** Antes de llegar al servicio principal, FastAPI valida que el dato sea correcto.
3. **Core (Django REST):** El serializador de Django rechaza cualquier petición manipulada con un error HTTP 400 (Bad Request).

### 🔑 Autenticación JWT

Usamos **tokens JWT firmados con RSA (RS256)**. auth-service firma los tokens con su llave privada, y los demás servicios los verifican con la llave pública. Esto significa que ningún servicio necesita compartir secretos — la llave pública es suficiente para confiar en la identidad del usuario.

### 🌐 Redes aisladas

El sistema tiene **3 redes Docker**:
- `public-gateway`: la cara visible, por donde entra el tráfico de usuarios
- `backend-mesh`: la red interna donde los servicios se comunican entre sí
- `data-isolated`: una red **totalmente aislada** (sin acceso externo) para bases de datos, Redis y RabbitMQ

Además, todos los servicios corren como usuarios no-root (`appuser`, uid 8888) para minimizar riesgos de seguridad.

---

## Interfaces de usuario

### 🛍️ TechMarket — Interfaz de Comprador

Un escaparate digital con diseño limpio y profesional (estilo SaaS premium). Usa la tipografía **Inter** para máxima legibilidad.
- Catálogo de productos con fotos, precios y ofertas destacadas
- Carrusel de imágenes para productos con múltiples fotos
- Carrito de compras que se guarda en el navegador (localStorage) por 7 días
- Actualización en vivo cada 5 segundos — si un producto se agota, desaparece solo
- Proceso de compra rápido: seleccionas productos, pones tu email y ¡listo!

### 🖥️ Cybercore — Interfaz de Proveedor

Un panel de control con estética **Cyberpunk / Dark Industrial**. Tipografías monoespaciadas (Orbitron + Share Tech Mono) y colores neón sobre fondo oscuro.
- Registro e inicio de sesión para proveedores
- Tabla de inventario que se actualiza sola cada 3 segundos
- Formulario para añadir productos: nombre, descripción (máx 250 caracteres, con contador en vivo), precio, oferta, fotos (hasta 7)
- Botones para reabastecer stock o eliminar productos
- Notificaciones visuales (toast) cuando algo sale bien o mal

---

## Mapeo completo de rutas

### Rutas externas (a través de Nginx, puerto 80)

| Método | Ruta | Servicio | Descripción |
|--------|------|----------|-------------|
| GET | `/comprador` | web-frontend | Catálogo de comprador (TechMarket) |
| POST | `/comprador/register` | web-frontend | Registro de comprador |
| POST | `/comprador/login` | web-frontend | Inicio de sesión comprador |
| POST | `/comprador/checkout` | web-frontend | Procesar compra |
| GET | `/comprador/logout` | web-frontend | Cerrar sesión comprador |
| GET | `/proveedor` | web-frontend | Panel de proveedor (Cybercore) |
| POST | `/proveedor/register` | web-frontend | Registro de proveedor |
| POST | `/proveedor/login` | web-frontend | Inicio de sesión proveedor |
| GET | `/proveedor/logout` | web-frontend | Cerrar sesión proveedor |
| POST | `/catalog/add` | web-frontend | Añadir producto |
| POST | `/catalog/restock/{id}` | web-frontend | Reabastecer producto |
| POST | `/catalog/delete/{id}` | web-frontend | Eliminar producto |
| GET | `/api/products/live` | web-frontend | Catálogo en vivo (JSON) |
| CUALQUIERA | `/api/auth/*` | auth-service | Endpoints de autenticación |
| CUALQUIERA | `/api/orders/*` | order-service | Endpoints de órdenes y catálogo |
| CUALQUIERA | `/media/*` | Nginx directo | Archivos multimedia (imágenes) |

### Rutas internas del auth-service (`/api/auth`)

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| POST | `/api/auth/register` | No | Registrar nuevo usuario |
| POST | `/api/auth/login` | No | Iniciar sesión (devuelve JWT) |
| POST | `/api/auth/verify` | Bearer Token | Verificar validez del token |
| GET | `/api/auth/proveedores/count` | No | Contar proveedores registrados |
| GET | `/api/auth/health` | No | Verificar que el servicio funciona |

### Rutas internas del order-service

| Método | Ruta | Autenticación | Descripción |
|--------|------|---------------|-------------|
| GET | `/api/orders/catalog/products/` | No | Listar productos (con caché) |
| POST | `/api/orders/catalog/products/` | Proveedor | Crear producto (con fotos) |
| GET | `/api/orders/catalog/products/{id}/` | No | Ver producto individual |
| PUT/PATCH/DELETE | `/api/orders/catalog/products/{id}/` | Proveedor | Actualizar o eliminar producto |
| POST | `/api/orders/checkout/` | Comprador | Crear orden de compra |

### Rutas internas del notification-service

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Verificar que el servicio funciona |

---

## Variables de entorno

### docker-compose.yml

| Variable | Valor |
|----------|-------|
| `POSTGRES_DB` | ecommerce_prod |
| `POSTGRES_USER` | postgres |
| `POSTGRES_PASSWORD` | super_secure_admin_root_password_2026 |
| `APP_DB_USER` | corporate_admin_user |
| `APP_DB_PASS` | strong_secure_password_2026 |
| `APP_DB_NAME` | ecommerce_prod |

### auth-service

| Variable | Valor |
|----------|-------|
| `SECRET_KEY` | global-corporate-secret-key-2026 |
| `DATABASE_URL` | sqlite:////app/db_data/auth.db |

### order-service y outbox-worker

| Variable | Valor |
|----------|-------|
| `DJANGO_SECRET_KEY` | django-secure-prod-key-2026 |
| `JWT_SECRET_KEY` | global-corporate-secret-key-2026 |
| `DJANGO_DEBUG` | False |
| `DB_NAME` | ecommerce_prod |
| `DB_USER` | corporate_admin_user |
| `DB_PASSWORD` | strong_secure_password_2026 |
| `DB_HOST` | postgres |
| `REDIS_URL` | redis://redis:6379/0 |
| `RABBITMQ_URL` | amqp://guest:guest@rabbitmq:5672/ |

### notification-service

| Variable | Valor |
|----------|-------|
| `RABBITMQ_URL` | amqp://guest:guest@rabbitmq:5672/ |
| `REDIS_URL` | redis://redis:6379/0 |

### web-frontend

| Variable | Valor |
|----------|-------|
| `AUTH_SERVICE_URL` | http://auth-service:5000 |
| `ORDER_SERVICE_URL` | http://order-service:8000 |
| `SECRET_KEY` | global-corporate-secret-key-2026 |
| `FRONTEND_SECRET_KEY` | prod-secret-key-2026 |

---

## Cómo levantar el proyecto en local

Necesitas tener instalado:
- **Docker Desktop** (versión 20.10 o superior)
- **Docker Compose** (versión 2.0 o superior)

Pasos:

```bash
# 1. Clona el repositorio
git clone https://github.com/RmedranoCh/E-Commerce-Marketplace-Corporativo.git
cd E-Commerce-Marketplace-Corporativo

# 2. Levanta todo el sistema
docker compose up --build -d
```

El sistema arrancará automáticamente todos los servicios en el orden correcto. PostgreSQL se inicializa con el usuario y base de datos necesarios, Django ejecuta sus migraciones, y todo queda listo para usar.

### Puertos de acceso

| URL | ¿Qué es? |
|-----|----------|
| http://localhost/comprador | Catálogo de comprador (TechMarket) |
| http://localhost/proveedor | Panel de proveedor (Cybercore) |
| http://localhost/admin | Administración Django de órdenes |
| http://localhost:15672 | Consola de RabbitMQ (usuario: guest / contraseña: guest) |

---

## Cómo funciona el flujo de una compra (paso a paso)

1. Un comprador navega el catálogo, ve productos con sus precios y fotos, y los añade al carrito.
2. Cuando decide comprar, ingresa su email y confirma la compra.
3. El **order-service** recibe la petición, verifica el stock disponible (bloqueando la fila del producto para que nadie más pueda comprarlo al mismo tiempo), descuenta el inventario y crea la orden.
4. Dentro de la misma transacción, se crea un evento en la tabla **Outbox** con todos los detalles del pedido.
5. El **outbox-worker** detecta el nuevo evento, lo publica en **RabbitMQ** y lo marca como procesado.
6. El **notification-service** recoge el mensaje de la cola, verifica en Redis que no lo haya procesado antes (idempotencia), y simula el envío de un correo de confirmación.
7. El comprador ve el resultado en pantalla sin necesidad de recargar la página.

Todo este proceso ocurre en cuestión de segundos, y está diseñado para que ningún pedido se pierda incluso si algún componente falla en el camino.

---

## Estructura del proyecto

```
├── auth-service/          # Servicio de autenticación (Flask + SQLite)
│   ├── app/
│   │   ├── models.py      # Modelo User (username, email, password, role)
│   │   ├── routes.py      # Blueprint con endpoints de auth
│   │   ├── auth.py        # Lógica JWT (RS256)
│   │   ├── private_key.pem
│   │   └── public_key.pem
│   ├── Dockerfile
│   └── requirements.txt
│
├── gateway/               # Proxy inverso Nginx
│   └── nginx.conf
│
├── notification-service/  # Servicio de notificaciones (FastAPI)
│   ├── app/
│   │   ├── main.py        # FastAPI app + consumer thread
│   │   ├── consumer.py    # Consumidor de RabbitMQ
│   │   ├── email_notifier.py  # Simulador de email
│   │   └── config.py      # Variables de entorno
│   ├── Dockerfile
│   └── requirements.txt
│
├── order-service/         # Core del negocio (Django REST)
│   ├── core/
│   │   ├── settings.py    # Config Django (PostgreSQL, Redis, JWT)
│   │   ├── urls.py        # Rutas principales
│   │   └── authentication.py  # Autenticación JWT personalizada
│   ├── catalog/
│   │   ├── models.py      # Modelo Product
│   │   ├── serializers.py # ProductSerializer
│   │   ├── views.py       # CRUD de productos
│   │   └── urls.py
│   ├── orders/
│   │   ├── models.py      # Order, OrderItem, OutboxEvent
│   │   ├── views.py       # CreateOrderView
│   │   └── urls.py
│   ├── publisher.py       # Outbox worker
│   ├── Dockerfile
│   ├── requirements.txt
│   └── public_key.pem     # Llave pública RSA para JWT
│
├── web-frontend/          # BFF (Backend for Frontend) - FastAPI
│   ├── app/
│   │   ├── main.py        # FastAPI app con rutas y templates
│   │   ├── jwt_utils.py   # Validación de JWT
│   │   ├── templates/     # Jinja2: index, comprador, proveedor
│   │   └── static/
│   │       ├── css/       # base.css, comprador.css, proveedor.css
│   │       └── js/        # JavaScript (carrito, polling, etc.)
│   ├── Dockerfile
│   └── requirements.txt
│
├── postgres-init/         # Script de inicialización de PostgreSQL
│   └── init-user-db.sh
│
├── docker-compose.yml     # Orquestación completa del sistema
└── .gitignore
```

---

## Licencia

Este proyecto está desarrollado con fines académicos y como demostración de una arquitectura de microservicios para comercio electrónico. Desarrollado y mantenido por **Rodrigo Medrano** © 2026.

---

---

# AliMarket & TechMarket — Corporate E-Commerce Marketplace

**Created by Rodrigo Medrano © 2026**

AliMarket (for buyers) and TechMarket (for sellers) form an e-commerce marketplace built to be robust, scalable, and secure. It follows a microservices architecture where each piece does its job independently yet coordinates seamlessly with the rest — like a finely tuned system.

The idea is simple yet powerful: buyers can browse products, check out deals, and make purchases; sellers can manage their inventory, add products, and control stock. Everything works in real time with automatic updates — no page reloads needed.

---

## System Architecture

Think of the system as a city with several specialized buildings. Each building (microservice) has a specific function, and they communicate through internal networks. Not everyone can enter every building — there's a security guard (Nginx) at the main entrance directing each person to the right place.

```
                  [ User Browser ]
                         |
                         ▼ (Port 80)
                 [ Nginx Gateway ]
                         |
        ┌────────────────┴────────────────┐
        ▼ /                               ▼ /api/
 [ web-frontend ]                  [ auth-service ]
 (FastAPI / BFF)                   (Flask / SQLite)
        |
        ▼ /api/orders/
 [ order-service ] ───► [ Outbox Event ] ───► [ outbox-worker ]
(Django REST / Postgres)                             |
        ▲                                          ▼ (AMQP)
        │                                    [ RabbitMQ Broker ]
        └─────────────── [ Redis Cache ]           |
                                                   ▼
                                        [ notification-service ]
```

### What does each component do?

#### 🚪 Nginx Gateway — The Digital Doorman
It's the single entry point to the system. When someone visits the site, Nginx receives the request and decides which service to forward it to based on the URL. It also serves images and media files directly for fast loading. It's configured with gzip compression, optimized buffers, and size limits to prevent abuse.

#### 🌐 web-frontend (BFF) — The Friendly Facade
Built with **FastAPI**, this service acts as the translator between the browser and the rest of the system. It renders HTML pages using Jinja2 and orchestrates calls to other services so you get everything you need in one response. This is where both the buyer interface (TechMarket) and the provider interface (Cybercore) are generated. It also manages session cookies with JWT tokens.

#### 🔐 auth-service — The Identity Guard
Built with **Flask** and an isolated **SQLite** database, it handles everything user-related: registration, login, and identity verification. It uses **JWT with asymmetric RS256 signing** (a public/private key pair) to generate tokens that expire after 2 hours. Users can be one of two types: **buyer** (comprador) or **provider/seller** (proveedor).

#### 📦 order-service — The Business Core
Powered by **Django 5.0 + Django REST Framework** with **PostgreSQL**, this service manages the product catalog, inventory, and purchase orders. It uses row-level locks (`select_for_update`) to prevent two people from buying the last item at the same time (race conditions). It also stores order events in a special **Outbox** table to make sure no order ever gets lost.

#### 📤 outbox-worker — The Reliable Mail Carrier
This is a Python worker running in its own container. Its job is simple but crucial: it constantly checks the Outbox table in PostgreSQL, picks up new order events (one by one, using locks to avoid conflicts), publishes them to **RabbitMQ**, and marks them as processed. This guarantees that every order triggers its notification, even if the system crashes midway.

#### 🐰 RabbitMQ — The Message Hub
This is the messaging system that receives order events and distributes them to the services that need to know about them. Everything flows through a queue called `pedido.creado` with persistent messages (they survive a RabbitMQ restart).

#### 🔔 notification-service — The Notifier
Written in **FastAPI**, this service consumes RabbitMQ messages and simulates sending order confirmation emails (in this version it prints to the console, but it's ready to connect to a real email service). It uses **Redis** to ensure each order is notified exactly once, even if duplicate messages arrive.

#### ⚡ Redis Cache — The Lightning-Fast Memory
Redis acts as a cache for the product catalog. When someone visits the store, products are loaded from Redis instead of hitting PostgreSQL, making everything much faster. The cache refreshes every 5 minutes and is automatically invalidated when a seller adds or modifies a product.

---

## Technologies Used

| Type | Technologies |
|------|-------------|
| **Backend** | Django 5.0, FastAPI 0.110, Flask 3.0, Django REST Framework 3.14 |
| **Databases** | PostgreSQL 15, Redis 7, SQLite |
| **Messaging** | RabbitMQ 3 (AMQP), Pika 1.3 |
| **Servers** | Docker, Docker Compose, Gunicorn, Uvicorn, Nginx |
| **Frontend** | HTML5, CSS3 (Flexbox/Grid), Vanilla JavaScript, Google Fonts (Inter, Orbitron, Share Tech Mono) |

---

## Security: How We Protect Data

### 🛡️ Cascading Firewall (3-Layer Validation)

A concrete example: product descriptions have a **250-character limit**. This limit is enforced at three different levels in case someone tries to bypass it:

1. **Browser (HTML5/JS):** The input field has `maxlength="250"` and a real-time counter that visually warns you as you approach the limit.
2. **BFF (FastAPI):** Before reaching the core service, FastAPI validates the data.
3. **Core (Django REST):** The Django serializer rejects any tampered request with an HTTP 400 (Bad Request) error.

### 🔑 JWT Authentication

We use **RSA-signed JWT tokens (RS256)**. The auth-service signs tokens with its private key, and other services verify them with the public key. This means no service needs to share secrets — the public key is enough to trust the user's identity.

### 🌐 Isolated Networks

The system has **3 Docker networks**:
- `public-gateway`: the visible face, where user traffic enters
- `backend-mesh`: the internal network where services communicate
- `data-isolated`: a **fully isolated network** (no external access) for databases, Redis, and RabbitMQ

All services run as non-root users (`appuser`, uid 8888) to minimize security risks.

---

## User Interfaces

### 🛍️ TechMarket — Buyer Interface

A digital storefront with a clean, professional design (SaaS premium style). Uses the **Inter** font for maximum readability.
- Product catalog with photos, prices, and highlighted deals
- Image carousel for products with multiple photos
- Shopping cart stored in the browser (localStorage) for 7 days
- Live updates every 5 seconds — if a product sells out, it disappears on its own
- Quick checkout: pick your products, enter your email, and you're done!

### 🖥️ Cybercore — Provider Interface

A control panel with a **Cyberpunk / Dark Industrial** aesthetic. Monospace fonts (Orbitron + Share Tech Mono) and neon colors on a dark background.
- Provider registration and login
- Inventory table that auto-updates every 3 seconds
- Product creation form: name, description (max 250 chars with live counter), price, offer, photos (up to 7)
- Buttons to restock or delete products
- Visual toast notifications for success or failure feedback

---

## Complete Route Map

### External Routes (via Nginx, port 80)

| Method | Route | Backend Service | Description |
|--------|-------|-----------------|-------------|
| GET | `/comprador` | web-frontend | Buyer catalog (TechMarket) |
| POST | `/comprador/register` | web-frontend | Buyer registration |
| POST | `/comprador/login` | web-frontend | Buyer login |
| POST | `/comprador/checkout` | web-frontend | Process checkout |
| GET | `/comprador/logout` | web-frontend | Buyer logout |
| GET | `/proveedor` | web-frontend | Provider panel (Cybercore) |
| POST | `/proveedor/register` | web-frontend | Provider registration |
| POST | `/proveedor/login` | web-frontend | Provider login |
| GET | `/proveedor/logout` | web-frontend | Provider logout |
| POST | `/catalog/add` | web-frontend | Add product |
| POST | `/catalog/restock/{id}` | web-frontend | Restock product |
| POST | `/catalog/delete/{id}` | web-frontend | Delete product |
| GET | `/api/products/live` | web-frontend | Live catalog (JSON) |
| ANY | `/api/auth/*` | auth-service | Authentication endpoints |
| ANY | `/api/orders/*` | order-service | Orders and catalog endpoints |
| ANY | `/media/*` | Nginx directly | Media files (images) |

### auth-service Internal Routes (`/api/auth`)

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| POST | `/api/auth/register` | No | Register a new user |
| POST | `/api/auth/login` | No | Login (returns JWT) |
| POST | `/api/auth/verify` | Bearer Token | Verify token validity |
| GET | `/api/auth/proveedores/count` | No | Count registered providers |
| GET | `/api/auth/health` | No | Health check |

### order-service Internal Routes

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/api/orders/catalog/products/` | No | List products (cached) |
| POST | `/api/orders/catalog/products/` | Provider | Create product (with images) |
| GET | `/api/orders/catalog/products/{id}/` | No | Get single product |
| PUT/PATCH/DELETE | `/api/orders/catalog/products/{id}/` | Provider | Update or delete product |
| POST | `/api/orders/checkout/` | Buyer | Create purchase order |

### notification-service Internal Route

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/health` | Health check |

---

## Environment Variables

### docker-compose.yml

| Variable | Value |
|----------|-------|
| `POSTGRES_DB` | ecommerce_prod |
| `POSTGRES_USER` | postgres |
| `POSTGRES_PASSWORD` | super_secure_admin_root_password_2026 |
| `APP_DB_USER` | corporate_admin_user |
| `APP_DB_PASS` | strong_secure_password_2026 |
| `APP_DB_NAME` | ecommerce_prod |

### auth-service

| Variable | Value |
|----------|-------|
| `SECRET_KEY` | global-corporate-secret-key-2026 |
| `DATABASE_URL` | sqlite:////app/db_data/auth.db |

### order-service and outbox-worker

| Variable | Value |
|----------|-------|
| `DJANGO_SECRET_KEY` | django-secure-prod-key-2026 |
| `JWT_SECRET_KEY` | global-corporate-secret-key-2026 |
| `DJANGO_DEBUG` | False |
| `DB_NAME` | ecommerce_prod |
| `DB_USER` | corporate_admin_user |
| `DB_PASSWORD` | strong_secure_password_2026 |
| `DB_HOST` | postgres |
| `REDIS_URL` | redis://redis:6379/0 |
| `RABBITMQ_URL` | amqp://guest:guest@rabbitmq:5672/ |

### notification-service

| Variable | Value |
|----------|-------|
| `RABBITMQ_URL` | amqp://guest:guest@rabbitmq:5672/ |
| `REDIS_URL` | redis://redis:6379/0 |

### web-frontend

| Variable | Value |
|----------|-------|
| `AUTH_SERVICE_URL` | http://auth-service:5000 |
| `ORDER_SERVICE_URL` | http://order-service:8000 |
| `SECRET_KEY` | global-corporate-secret-key-2026 |
| `FRONTEND_SECRET_KEY` | prod-secret-key-2026 |

---

## How to Run Locally

You'll need:
- **Docker Desktop** (v20.10+)
- **Docker Compose** (v2.0+)

Steps:

```bash
# 1. Clone the repository
git clone https://github.com/RmedranoCh/E-Commerce-Marketplace-Corporativo.git
cd E-Commerce-Marketplace-Corporativo

# 2. Start the entire system
docker compose up --build -d
```

The system will automatically start all services in the correct order. PostgreSQL initializes with the required user and database, Django runs its migrations, and everything is ready to use.

### Access URLs

| URL | What it is |
|-----|------------|
| http://localhost/comprador | Buyer catalog (TechMarket) |
| http://localhost/proveedor | Provider panel (Cybercore) |
| http://localhost/admin | Django order administration |
| http://localhost:15672 | RabbitMQ console (user: guest / password: guest) |

---

## How a Purchase Works (Step by Step)

1. A buyer browses the catalog, sees products with prices and photos, and adds them to the cart.
2. When they decide to buy, they enter their email and confirm the purchase.
3. The **order-service** receives the request, checks available stock (locking the product row so no one else can buy it simultaneously), decrements inventory, and creates the order.
4. Within the same transaction, an event is created in the **Outbox** table with all the order details.
5. The **outbox-worker** detects the new event, publishes it to **RabbitMQ**, and marks it as processed.
6. The **notification-service** picks up the message from the queue, checks Redis to make sure it hasn't been processed before (idempotency), and simulates sending a confirmation email.
7. The buyer sees the result on screen without needing to reload the page.

This whole process happens in seconds and is designed so that no order is ever lost, even if some component fails along the way.

---

## Project Structure

```
├── auth-service/          # Authentication service (Flask + SQLite)
│   ├── app/
│   │   ├── models.py      # User model (username, email, password, role)
│   │   ├── routes.py      # Auth endpoint Blueprint
│   │   ├── auth.py        # JWT logic (RS256)
│   │   ├── private_key.pem
│   │   └── public_key.pem
│   ├── Dockerfile
│   └── requirements.txt
│
├── gateway/               # Nginx reverse proxy
│   └── nginx.conf
│
├── notification-service/  # Notification service (FastAPI)
│   ├── app/
│   │   ├── main.py        # FastAPI app + consumer thread
│   │   ├── consumer.py    # RabbitMQ consumer
│   │   ├── email_notifier.py  # Email simulator
│   │   └── config.py      # Environment variables
│   ├── Dockerfile
│   └── requirements.txt
│
├── order-service/         # Business core (Django REST)
│   ├── core/
│   │   ├── settings.py    # Django config (PostgreSQL, Redis, JWT)
│   │   ├── urls.py        # Main routes
│   │   └── authentication.py  # Custom JWT authentication
│   ├── catalog/
│   │   ├── models.py      # Product model
│   │   ├── serializers.py # ProductSerializer
│   │   ├── views.py       # Product CRUD
│   │   └── urls.py
│   ├── orders/
│   │   ├── models.py      # Order, OrderItem, OutboxEvent
│   │   ├── views.py       # CreateOrderView
│   │   └── urls.py
│   ├── publisher.py       # Outbox worker
│   ├── Dockerfile
│   ├── requirements.txt
│   └── public_key.pem     # RSA public key for JWT
│
├── web-frontend/          # BFF (Backend for Frontend) - FastAPI
│   ├── app/
│   │   ├── main.py        # FastAPI with routes and templates
│   │   ├── jwt_utils.py   # JWT validation
│   │   ├── templates/     # Jinja2: index, comprador, proveedor
│   │   └── static/
│   │       ├── css/       # base.css, comprador.css, proveedor.css
│   │       └── js/        # JavaScript (cart, polling, etc.)
│   ├── Dockerfile
│   └── requirements.txt
│
├── postgres-init/         # PostgreSQL initialization script
│   └── init-user-db.sh
│
├── docker-compose.yml     # Full system orchestration
└── .gitignore
```

---

## License

This project is developed for academic purposes and as a demonstration of microservices architecture for e-commerce. Developed and maintained by **Rodrigo Medrano** © 2026.
