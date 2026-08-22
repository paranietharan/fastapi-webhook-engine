import uuid
from datetime import datetime
from pydantic import BaseModel, HttpUrl
from app.models.webhook import WebhookStatus

class WebhookIngestRequest(BaseModel):
    event_type: str
    target_url: HttpUrl
    payload: dict

class WebhookIngestResponse(BaseModel):
    delivery_id: uuid.UUID
    status: WebhookStatus
    created_at: datetime

    class Config:
        from_attributes = True