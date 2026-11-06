"""Retry queues hold messages until RabbitMQ dead-letters them for delivery."""
import json
import aio_pika

DELIVERY_QUEUE = "webhook_delivery_queue"
DLQ = "webhook_dlq"


def calculate_backoff_delay(attempt: int, base_delay: float = 2.0, max_delay: float = 300.0) -> int:
    """Fixed, bounded milliseconds per attempt; all messages in a queue share a TTL."""
    if attempt < 0 or base_delay <= 0 or max_delay <= 0:
        raise ValueError("attempt must be nonnegative and delays must be positive")
    return int(min(max_delay, base_delay * (2 ** min(attempt, 30))) * 1000)


async def handle_retry_or_dlq(
    channel: aio_pika.RobustChannel,
    message_data: dict,
    attempt: int,
    max_attempts: int = 5,
):
    if attempt < 0 or max_attempts < 1:
        raise ValueError("invalid attempt limits")
    next_attempt = attempt + 1
    payload = {**message_data, "attempt": next_attempt}
    if next_attempt >= max_attempts:
        routing_key = DLQ
        await channel.declare_queue(DLQ, durable=True)
    else:
        delay_ms = calculate_backoff_delay(next_attempt)
        # Separate queue per delay prevents short retries waiting behind longer ones.
        routing_key = f"webhook_retry_{next_attempt}_{delay_ms}ms"
        await channel.declare_queue(
            routing_key,
            durable=True,
            arguments={
                "x-message-ttl": delay_ms,
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": DELIVERY_QUEUE,
            },
        )
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload).encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=routing_key,
        mandatory=True,
    )
