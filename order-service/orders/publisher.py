import os
import sys
import time
import json
import pika
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings
from django.db import transaction, connections
from orders.models import OutboxEvent

def relay_outbox_events():
    params = pika.URLParameters(settings.RABBITMQ_URL)
    rabbitmq_connection = None
    channel = None
    
    while True:
        connections.close_all()
        hay_eventos = False
        try:
            if not rabbitmq_connection or rabbitmq_connection.is_closed:
                rabbitmq_connection = pika.BlockingConnection(params)
                channel = rabbitmq_connection.channel()
                channel.queue_declare(queue='pedido.creado', durable=True)
                channel.confirm_delivery()
                
            with transaction.atomic():
                events = list(
                    OutboxEvent.objects.select_for_update(skip_locked=True)
                    .filter(processed=False)
                    .order_by('created_at')[:50]
                )
                if events:
                    hay_eventos = True
                    sent_events = []
                    for event in events:
                        try:
                            channel.basic_publish(
                                exchange='',
                                routing_key='pedido.creado',
                                body=json.dumps(event.payload),
                                properties=pika.BasicProperties(delivery_mode=2, content_type='application/json')
                            )
                            event.processed = True
                            sent_events.append(event)
                        except pika.exceptions.UnroutableError:
                            continue
                            
                    if sent_events:
                        OutboxEvent.objects.bulk_update(sent_events, ['processed'])
            
            if not hay_eventos:
                time.sleep(1.0)
            else:
                time.sleep(0.1)
                
        except (pika.exceptions.AMQPError, Exception) as e:
            if rabbitmq_connection and not rabbitmq_connection.is_closed:
                try: rabbitmq_connection.close()
                except Exception: pass
            rabbitmq_connection = None
            time.sleep(5.0)

if __name__ == '__main__':
    relay_outbox_events()