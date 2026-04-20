import pika
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://chaos:chaos123@db:5432/chaosdb"


def callback(ch, method, properties, body):
    # BUG: Her mesajda yeni engine + session oluşturuluyor
    # Yüksek throughput'ta connection limiti aşılır
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        event = json.loads(body)
        print(f"[*] Processing event: {event['event_type']} for order {event['order_id']}")

        if event["event_type"] == "order_paid":
            print(f"[*] Sending confirmation email to {event['payload']['customer_email']}")
            print(f"[*] Order total: ${event['payload']['total']:.2f}")

        # BUG: Hata olursa mesaj kaybolur — basic_ack her zaman çağrılıyor
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"[!] Error processing message: {e}")
        # BUG: Nack/reject yok — hatalı mesaj DLQ'ya gitmez, kaybolur
        ch.basic_ack(delivery_tag=method.delivery_tag)
    finally:
        db.close()
        engine.dispose()


def main():
    # BUG: Retry yok — RabbitMQ hazır değilse crash
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="rabbitmq")
    )
    channel = connection.channel()

    # BUG: durable=False ile tutarlı olmalı ama queue kaybolur
    channel.queue_declare(queue="order_events", durable=False)

    # BUG: prefetch_count yok — tüm mesajları bir anda çeker, memory şişer
    channel.basic_consume(queue="order_events", on_message_callback=callback)

    print("[*] Worker started. Waiting for order events...")
    channel.start_consuming()


if __name__ == "__main__":
    main()
