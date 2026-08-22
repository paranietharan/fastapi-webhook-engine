from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.v1.events import router as events_router
from app.core.rabbitmq import rabbitmq_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to RabbitMQ
    await rabbitmq_client.connect()
    yield
    # Shutdown: Close connections cleanly
    await rabbitmq_client.close()

app = FastAPI(
    title="async-webhook-relay",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(events_router)

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}