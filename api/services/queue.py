import pika
import json


def get_rabbitmq_connection():
    # BUG: Retry yok — RabbitMQ henüz hazır değilse bağlantı başarısız olur
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="rabbitmq")
    )
    return connection


def publish_order_event(order_id: int, event_type: str, payload: dict):
    connection = get_rabbitmq_connection()
    channel = connection.channel()

    # BUG: durable=False — RabbitMQ restart olursa queue ve mesajlar kaybolur
    channel.queue_declare(queue="order_events", durable=False)

    message = json.dumps({
        "order_id": order_id,
        "event_type": event_type,
        "payload": payload,
    })

    # BUG: delivery_mode=1 (non-persistent) — mesaj diske yazılmaz
    channel.basic_publish(
        exchange="",
        routing_key="order_events",
        body=message,
        properties=pika.BasicProperties(delivery_mode=1),
    )

    connection.close()
