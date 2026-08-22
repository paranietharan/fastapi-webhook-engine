import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rabbitmq import rabbitmq_client
from app.models.webhook import WebhookEvent, WebhookStatus
from app.schemas.webhook import WebhookIngestRequest, WebhookIngestResponse

router = APIRouter(prefix="/api/v1", tags=["Events"])

@router.post(
    "/events",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=WebhookIngestResponse,
)
async def ingest_event(
    event_in: WebhookIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    delivery_id = uuid.uuid4()

    # 1. Store canonical state in PostgreSQL
    event_record = WebhookEvent(
        id=delivery_id,
        event_type=event_in.event_type,
        target_url=str(event_in.target_url),
        payload=event_in.payload,
        status=WebhookStatus.PENDING,
        attempts=0,
    )
    db.add(event_record)
    await db.commit()
    await db.refresh(event_record)

    # 2. Enqueue delivery task into RabbitMQ
    message_payload = {
        "delivery_id": str(delivery_id),
        "event_type": event_record.event_type,
        "target_url": str(event_record.target_url),
        "payload": event_record.payload,
        "attempt": 0,
    }
    await rabbitmq_client.publish_event(message_payload)

    return event_record