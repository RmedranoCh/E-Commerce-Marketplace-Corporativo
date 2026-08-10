# AliMarket & TechMarket — Corporate E-Commerce Marketplace

An e-commerce marketplace built on a microservices architecture. AliMarket (for buyers) and TechMarket (for providers) run in a single system where each piece does its job independently yet works in coordination: buyers browse products, build their cart, and buy in real time; sellers manage their inventory, publish products, and control stock.

---

## System architecture

The system is organized as microservices that talk to each other over internal networks. An Nginx gateway is the single entry point and routes each request to the right service.

```
[ User Browser ]
        |
        ▼ (Port 80)
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

### Components

| Component | What it does |
|------------|------------|
| **Nginx Gateway** | Single entry point. Routes traffic by URL and serves images and media files. |
| **web-frontend (BFF)** | FastAPI that renders the pages (Jinja2) and orchestrates calls to the other services. Handles JWT login. |
| **auth-service** | Flask + isolated SQLite. Registration, login, and identity verification with RS256-signed JWT. Roles: buyer and provider. |
| **order-service** | Django 5 + DRF + PostgreSQL. Catalog, inventory, and orders. Uses row-level locks (`select_for_update`) and the Outbox pattern. |
| **outbox-worker** | Watches the Outbox table, publishes order events to RabbitMQ, and marks them as processed. |
| **RabbitMQ** | Message broker. Distributes order events through the `pedido.creado` queue. |
| **notification-service** | Consumes messages and simulates sending confirmation emails (ready to connect a real service). |
| **Redis** | Catalog cache and notification idempotency control. |

---

## Features

- **Real-time shopping**: when a product sells out, it disappears from the catalog without a page reload.
- **Persistent cart** in the browser (localStorage) for 7 days.
- **Provider panel** (Cybercore) with a cyberpunk look: self-updating inventory, product creation with photos, restocking, and removal.
- **3-layer validation**: browser, BFF, and core (for example, a product description has a 250-character limit enforced at every level).
- **JWT authentication with RSA (RS256)**: auth-service signs, other services verify with the public key. No shared secrets.
- **Isolated Docker networks**: `public-gateway`, `backend-mesh`, and `data-isolated` (databases with no external access). All services run as a non-root user.
- **No order ever gets lost**: the Outbox pattern + RabbitMQ guarantee notifications even if a service goes down.

---

## Tech stack

| Type | Technologies |
|------|-------------|
| **Backend** | Django 5.0, FastAPI 0.110, Flask 3.0, Django REST Framework 3.14 |
| **Databases** | PostgreSQL 15, Redis 7, SQLite |
| **Messaging** | RabbitMQ 3 (AMQP), Pika 1.3 |
| **Servers** | Docker Compose, Gunicorn, Uvicorn, Nginx |
| **Frontend** | HTML5, CSS3 (Flexbox/Grid), vanilla JavaScript, Google Fonts (Inter, Orbitron, Share Tech Mono) |

---

## Project structure

```
ecommerce-marketplace/
├── auth-service/          # Authentication service (Flask + SQLite)
├── gateway/               # Nginx reverse proxy
├── notification-service/  # Notification service (FastAPI + RabbitMQ)
├── order-service/         # Business core (Django REST + PostgreSQL)
├── web-frontend/          # BFF (FastAPI + Jinja2)
├── postgres-init/         # PostgreSQL initialization script
├── docker-compose.yml     # Full orchestration
├── .env.example           # Environment variable template (no secrets)
└── .gitignore
```

---

## Getting started

### Requirements

- **Docker Desktop** (version 20.10 or later).
- **Docker Compose** (version 2.0 or later).

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/RmedranoCh/E-Commerce-Marketplace-Corporativo.git
cd E-Commerce-Marketplace-Corporativo

# 2. Start the entire system
docker compose up --build -d
```

The system starts all services in order: PostgreSQL initializes its user and database, Django runs the migrations, and everything is ready to use.

> Sensitive values are defined in `.env` (ignored by Git). See `.env.example` for the full list of variables.

### Access URLs

| URL | What it is |
|-----|------------|
| http://localhost/comprador | Buyer catalog (TechMarket) |
| http://localhost/proveedor | Provider panel (Cybercore) |
| http://localhost/admin | Django order administration |
| http://localhost:15672 | RabbitMQ console (guest / guest) |

---

## How a purchase works

1. The buyer browses the catalog and adds products to the cart.
2. On checkout, `order-service` validates stock (locks the product row to avoid race conditions), decrements inventory, and creates the order.
3. An event is created in the **Outbox** table within the same transaction.
4. `outbox-worker` detects the event, publishes it to **RabbitMQ**, and marks it as processed.
5. `notification-service` consumes the message, checks Redis for duplicates, and simulates the confirmation email.
6. The buyer sees the result on screen without a reload.

---

## Tests

Each microservice includes unit tests with **pytest** covering its critical flows (authentication, catalog validation, BFF routes, and notifications). They run **without Docker or external services**: they use temporary SQLite databases and mock the upstream services.

```bash
# 1. Install development dependencies (once)
pip install -r requirements-dev.txt

# 2. Run the tests for each microservice
cd auth-service && python -m pytest tests -v
cd order-service && python -m pytest tests -v
cd web-frontend && python -m pytest tests -v
cd notification-service && python -m pytest tests -v
```

> `requirements-dev.txt` pins minimum versions compatible with Python 3.13. To reproduce the exact production environment, use each service's `requirements.txt` (Docker images).

---

## License

Project developed for academic purposes and as a demonstration of microservices architecture for e-commerce. Developed and maintained by **Rodrigo Medrano** © 2026.

---

Prefer Spanish? → [README.md](README.md)