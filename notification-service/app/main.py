import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.consumer import start_rabbitmq_consumer

@asynccontextmanager
async def lifespan(app: FastAPI):
    consumer_thread = threading.Thread(target=start_rabbitmq_consumer, daemon=True)
    consumer_thread.start()
    print("[FASTAPI] Hilo del consumidor de RabbitMQ inicializado de fondo en modo asíncrono.")
    yield
    print("[FASTAPI] Apagando el servicio de notificaciones corporativo.")

app = FastAPI(
    title="Notification & Shipping Corporate Daemon", 
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "notification-service"}