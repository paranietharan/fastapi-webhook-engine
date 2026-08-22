import random
import json
import aio_pika

def calculate_backoff_delay(attempt: int, base_delay: float = 2.0, max_delay: float = 300.0) -> int:
    """Calculates exponential backoff with full jitter in milliseconds for AMQP TTL."""
    exponential = min(max_delay, base_delay * (2 ** attempt))
    jitter = random.uniform(0.5, 1.5)
    delay_seconds = exponential * jitter
    return int(delay_seconds * 1000) # Convert to ms for RabbitMQ

async def handle_retry_or_dlq(
    channel: aio_pika.RobustChannel,
    message_data: dict,
    attempt: int,
    max_attempts: int = 5,
):
    next_attempt = attempt + 1
    message_data["attempt"] = next_attempt

    if next_attempt >= max_attempts:
        # Route to Dead Letter Queue
        dlq_message = aio_pika.Message(
            body=json.dumps(message_data).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await channel.default_exchange.publish(dlq_message, routing_key="webhook_dlq")
    else:
        # Re-publish back to delivery queue (or delayed exchange)
        delay_ms = calculate_backoff_delay(next_attempt)
        retry_message = aio_pika.Message(
            body=json.dumps(message_data).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            expiration=str(delay_ms), # Message TTL
        )
        await channel.default_exchange.publish(retry_message, routing_key="webhook_delivery_queue")