import time
import pika
import json
import redis
from app.config import settings
from app.email_notifier import EmailNotifier

def start_rabbitmq_consumer():
    rabbitmq_params = pika.URLParameters(settings.RABBITMQ_URL)
    redis_client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=5, retry_on_timeout=True)
    
    while True:
        try:
            connection = pika.BlockingConnection(rabbitmq_params)
            channel = connection.channel()
            channel.queue_declare(queue='pedido.creado', durable=True)
            
            def callback(ch, method, properties, body):
                idempotency_key = None
                try:
                    event_data = json.loads(body)
                    order_id = event_data.get('order_id')
                    email = event_data.get('email')
                    total_raw = event_data.get('total')
                    raw_items = event_data.get('items', [])
                    
                    if not order_id or not email:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                        return
                    
                    try:
                        total = float(total_raw) if total_raw else 0.0
                    except (ValueError, TypeError):
                        total = 0.0

                    processed_items = []
                    for item in raw_items:
                        if isinstance(item, dict):
                            processed_items.append(f"{item.get('name', 'Articulo')} (x{item.get('quantity', 1)})")
                        else:
                            processed_items.append(str(item))
                    
                    idempotency_key = f"processed_order:{order_id}"
                    is_new_event = redis_client.set(idempotency_key, "processed", ex=86400, nx=True)
                    
                    if not is_new_event:
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        return
                    
                    EmailNotifier.send_order_confirmation(
                        email=email, order_id=order_id, total=total, items=processed_items
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    
                except json.JSONDecodeError:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                except redis.exceptions.ConnectionError:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                    time.sleep(2)
                except Exception:
                    if idempotency_key:
                        try: redis_client.delete(idempotency_key)
                        except Exception: pass
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                    time.sleep(2)
            
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue='pedido.creado', on_message_callback=callback)
            channel.start_consuming()
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.ConnectionClosedByBroker):
            time.sleep(5)
        except Exception:
            time.sleep(5)