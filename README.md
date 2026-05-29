🚀 **AliMarket & TechMarket — E-Commerce Marketplace Corporativo**
Plataforma de comercio electrónico de grado corporativo basada en una arquitectura de Microservicios distribuidos, altamente concurrentes y tolerantes a fallos. El sistema implementa patrones avanzados de diseño de software para garantizar el aislamiento de responsabilidades, la consistencia eventual y la seguridad perimetral de extremo a extremo.
🏗️ **Arquitectura del Sistema**
El ecosistema está fragmentado en componentes independientes orquestados mediante Docker, comunicados a través de redes virtuales internas y protegidos en una zona aislada de datos.

                  [ Navegador del Usuario ]
                             │
                             ▼ (Puerto 80)
                     [ Nginx Gateway ]
                             │
            ┌────────────────┴────────────────┐
            ▼ /                               ▼ /api/
     [ web-frontend ]                  [ auth-service ]
     (FastAPI / BFF)                   (Flask / SQLite)
            │
            ▼ /api/orders/
     [ order-service ] ───► [ Outbox Event ] ───► [ outbox-worker ]
  (Django REST / Postgres)                             │
            ▲                                          ▼ (AMQP)
            │                                    [ RabbitMQ Broker ]
            └─────────────── [ Redis Cache ]           │
                                                       ▼
                                            [ notification-service ]

🛰️ **Componentes Clave**
1. *Nginx Reverse Proxy & Gateway:* Único punto de entrada perimetral público. Maneja el balanceo de carga, enrutamiento reverso y el despacho optimizado de recursos multimedia (/media/).
2. *web-frontend (BFF - Backend for Frontend):* Desarrollado en FastAPI. Actúa como una capa perimetral asíncrona que consume, unifica y optimiza las respuestas de los microservicios core para renderizarlas de manera eficiente en el cliente.
3. *auth-service:* Microservicio dedicado a la gobernanza de accesos mediante JWT (JSON Web Tokens) y firmas asimétricas. Implementa una base de datos SQLite aislada para almacenar de manera perimetral las credenciales corporativas.
4. *order-service:* Core del negocio desarrollado en Django REST Framework. Gestiona el catálogo de productos e inventarios sobre una base de datos transaccional PostgreSQL, utilizando bloqueos de fila (select_for_update) para mitigar condiciones de carrera concurrentes.
5. *Transactional Outbox Worker:* Worker asíncrono en Python encargado de leer de manera atómica los eventos consolidados en la base de datos de órdenes y propagarlos de forma garantizada hacia el bus de mensajería.
6. *RabbitMQ Message Broker:* Sistema centralizado de mensajería que distribuye eventos en tiempo real bajo el estándar AMQP, desacoplando los flujos de facturación de los servicios secundarios.
7. *notification-service:* Microservicio reactivo que consume las colas del broker para disparar alertas del sistema de forma distribuida.
8. *Redis Cache:* Capa de memoria intermedia en red aislada que optimiza los tiempos de respuesta del catálogo general, reduciendo la carga transaccional directa sobre la base de datos principal.

🛡️ **Seguridad y Diseño del Frontend**
🔒 **Validaciones en Cascada (Cascading Data Firewall)**
El sistema implementa un mecanismo rígido de seguridad y optimización para los strings de datos (como la descripción técnica de los componentes limitada estrictamente a 250 caracteres), validada en tres capas críticas:
* *Capa 1 (Client-Side HTML5/JS):* Restricción física mediante atributos nativos maxlength="250" acompañados de un contador de buffer dinámico en tiempo real que alerta al proveedor visualmente antes del desborde.
* *Capa 2 (Edge Gateway / BFF):* FastAPI actúa como un cortafuegos perimetral que intercepta y convalida los payloads entrantes.
* *Capa 3 (Core API / Serializer):* Django REST Framework utiliza validadores atómicos de deserialización (ProductSerializer) que rechazan con códigos HTTP 400 (Bad Request) cualquier petición directa manipulada que intente evadir los límites establecidos.

🎨 **Frontend Nítido de Alta Legibilidad**
* **Módulo Comprador:** Diseñado bajo una estética SaaS premium con la tipografía de alta visibilidad Inter, implementando técnicas de truncado inteligente por CSS (-webkit-line-clamp) que garantizan que descripciones extensas nunca deformen la simetría de la grilla del catálogo.
* **Módulo Proveedor:** Panel operativo de estética Cyberpunk / Dark Industrial diseñado con tipografías monoespaciadas legibles, componentes de alta interacción visual y sincronización asíncrona en tiempo real mediante Polling adaptativo.

🛠️ **Tecnologías Utilizadas**
* *Backend Frameworks:* Django 5.0, FastAPI, Django REST Framework.
* *Bases de Datos & Caché:* PostgreSQL 15, Redis 5.0, SQLite.
* *Mensajería Asíncrona:* RabbitMQ (AMQP Protocol), Pika.
* *Servidores & Orquestación:* Docker, Docker Compose, Gunicorn, Uvicorn, Nginx.
* *Frontend Stack:* HTML5, CSS Moderno (Flexbox / Grid), JavaScript Asíncrono Nativo, Google Fonts.

🚀 **Instrucciones de Despliegue Local**
**Requisitos Previos**
* Docker Desktop instalado (v20.10+ recomendado)
* Docker Compose (v2.0+)
**Pasos para Levantar el Clúster**
1. Clona este repositorio en tu entorno local:
git clone https://github.com/RmedranoCh/E-Commerce-Marketplace-Corporativo.git
cd tu-repositorio
2. Ejecuta la compilación y el levantamiento de los contenedores distribuidos en segundo plano:
docker compose up --build -d
3. El orquestador configurará automáticamente las redes internas virtuales (public-gateway, backend-mesh y data-isolated), inicializará los accesos de alta concurrencia en PostgreSQL y ejecutará las migraciones atómicas de Django.
**Puertos de Acceso Locales**
* Catálogo del Comprador (TechMarket): http://localhost/comprador
* Terminal del Proveedor (Cybercore): http://localhost/proveedor
* Administrador de Base de Datos de Órdenes: http://localhost/admin
* Panel de Control de RabbitMQ: http://localhost:15672 (Credenciales por defecto: guest / guest)

📝 **Licencia**
Este proyecto está desarrollado bajo fines académicos y emulación industrial. Desarrollado y mantenido por Rodrigo Medrano © 2026.