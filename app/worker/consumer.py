import asyncio
import json
import uuid
import logging
import aio_pika
import httpx
from app.core.config import settings
from app.worker.dispatcher import dispatch_webhook
from app.worker.retry import handle_retry_or_dlq

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker")

async def main():
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=20)

    queue = await channel.declare_queue("webhook_delivery_queue", durable=True)
    await channel.declare_queue("webhook_dlq", durable=True)

    limits = httpx.Limits(max_keepalive_connections=50, max_connections=200)
    logger.info("Worker started. Listening for messages on 'webhook_delivery_queue'...")
    async with httpx.AsyncClient(limits=limits) as http_client:
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process(requeue=False, ignore_processed=True):
                    payload_data = json.loads(message.body.decode("utf-8"))
                    delivery_id = uuid.UUID(payload_data["delivery_id"])
                    target_url = payload_data["target_url"]
                    payload = payload_data["payload"]
                    attempt = payload_data.get("attempt", 0)

                    logger.info(f"Received delivery {delivery_id} to {target_url} (Attempt {attempt})")

                    success_or_terminal = await dispatch_webhook(
                        delivery_id=delivery_id,
                        target_url=target_url,
                        payload=payload,
                        attempt=attempt,
                        http_client=http_client,
                    )

                    if not success_or_terminal:
                        try:
                            await handle_retry_or_dlq(channel, payload_data, attempt)
                        except Exception:
                            # Keep the original delivery if publishing the retry failed.
                            await message.nack(requeue=True)
                            logger.exception("Retry publication failed; original delivery requeued")

if __name__ == "__main__":
    asyncio.run(main())