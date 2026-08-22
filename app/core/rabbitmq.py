import json
import aio_pika
from app.core.config import settings

class RabbitMQClient:
    def __init__(self):
        self.connection: aio_pika.RobustConnection | None = None
        self.channel: aio_pika.RobustChannel | None = None

    async def connect(self):
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=10)

        # Declare the primary delivery queue & DLQ
        await self.channel.declare_queue("webhook_delivery_queue", durable=True)
        await self.channel.declare_queue("webhook_dlq", durable=True)

    async def publish_event(self, payload: dict, routing_key: str = "webhook_delivery_queue"):
        if not self.channel:
            raise RuntimeError("RabbitMQ channel is not initialized.")

        message = aio_pika.Message(
            body=json.dumps(payload).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await self.channel.default_exchange.publish(message, routing_key=routing_key)

    async def close(self):
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()

rabbitmq_client = RabbitMQClient()