import os

class Settings:
    RABBITMQ_URL: str = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
    
    REDIS_URL: str = os.getenv('REDIS_URL', 'redis://redis:6379/0')

settings = Settings()