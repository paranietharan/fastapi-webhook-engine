import time
import uuid
import logging
from datetime import datetime, timezone
import httpx
from sqlalchemy import select
from app.core.database import async_session_factory
from app.core.redis import redis_client
from app.models.webhook import WebhookEvent, WebhookDeliveryLog, WebhookStatus

logger = logging.getLogger("worker.dispatcher")

async def dispatch_webhook(
    delivery_id: uuid.UUID,
    target_url: str,
    payload: dict,
    attempt: int,
    http_client: httpx.AsyncClient,
) -> bool:
    """
    Returns True if delivery succeeded (2xx) or reached terminal state without retry needed.
    Returns False if transient failure occurred and needs requeue/backoff.
    """
    lock_key = f"lock:delivery:{delivery_id}"
    
    # Acquire atomic Redis lock (30s TTL)
    # TODO: make the time as cofigurable
    is_acquired = await redis_client.set(lock_key, "locked", nx=True, ex=30)
    if not is_acquired:
        logger.warning(f"Delivery {delivery_id} is currently locked by another worker. Skipping.")
        # Another worker is actively processing this delivery
        return True

    start_time = time.monotonic()
    http_status = 0
    response_text = None
    error_message = None
    is_success = False

    try:
        response = await http_client.post(
            target_url,
            json=payload,
            headers={"Content-Type": "application/json", "X-Delivery-ID": str(delivery_id)},
            timeout=5.0,
        )
        http_status = response.status_code
        response_text = response.text[:1000] # TODO: make the response size as configurable
        is_success = 200 <= http_status < 300
    except httpx.TimeoutException as exc:
        error_message = f"Timeout: {str(exc)}"
    except httpx.RequestError as exc:
        error_message = f"Network Request Error: {str(exc)}"
    except Exception as exc:
        error_message = f"Unexpected Error: {str(exc)}"
    finally:
        execution_time_ms = int((time.monotonic() - start_time) * 1000)
        
        if is_success:
            logger.info(f"Delivery {delivery_id} succeeded in {execution_time_ms}ms (HTTP {http_status})")
        else:
            logger.error(f"Delivery {delivery_id} failed in {execution_time_ms}ms. Error: {error_message or f'HTTP {http_status}'}")

    # 2. Update PostgreSQL canonical state and write attempt log
    async with async_session_factory() as db:
        async with db.begin():
            stmt = select(WebhookEvent).where(WebhookEvent.id == delivery_id)
            result = await db.execute(stmt)
            event = result.scalar_one_or_none()

            if event:
                event.attempts = attempt + 1
                
                if is_success:
                    event.status = WebhookStatus.DELIVERED
                    event.next_retry_at = None
                elif event.attempts >= event.max_attempts or (400 <= http_status < 500):
                    # 4xx client errors or exhausted retries -> terminal FAILED
                    event.status = WebhookStatus.FAILED
                    event.next_retry_at = None
                else:
                    # Transient error (5xx or timeout) -> RETRYING
                    event.status = WebhookStatus.RETRYING

                # Append immutable delivery log
                log = WebhookDeliveryLog(
                    event_id=delivery_id,
                    http_status=http_status,
                    response_body=response_text,
                    error_log=error_message,
                    attempt_num=attempt + 1,
                    execution_time_ms=execution_time_ms,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(log)

    # Release Redis lock
    await redis_client.delete(lock_key)
    return is_success or (event and event.status == WebhookStatus.FAILED)