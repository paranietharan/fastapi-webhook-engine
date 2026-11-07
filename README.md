# FastAPI Webhook Engine

A robust, asynchronous webhook ingestion and delivery engine using FastAPI, PostgreSQL, RabbitMQ, and Redis.

## 1. Setup Environment

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Start Services

Start the required infrastructure (PostgreSQL, RabbitMQ, Redis) using Docker:

```bash
docker compose up -d
```

## 3. Database Migrations

Apply the database migrations to create the necessary tables in PostgreSQL:

```bash
alembic upgrade head
```

*(Note: If you need to generate new migrations after changing models, run: `alembic revision --autogenerate -m "description"`)*

## 4. Run the Application

You need to run two processes simultaneously (in separate terminal tabs). Make sure your virtual environment is activated in both!

**Start the API Server (Ingestion):**
```bash
uvicorn app.main:app --reload
```

**Start the Worker (Delivery):**
```bash
python -m app.worker.consumer
```

## Sample request
Health
```bash
curl --location 'localhost:8000/health'
```

```bash
curl --location 'localhost:8000/api/v1/events' \
--data '{
    "event_type": "order.created",
    "target_url": "<webhook_url>",
    "payload": {
        "order_id": 12345,
        "amount": 99.99
    }
}'
```

## Retry delivery and verification

Retries use durable queues with a fixed queue-level TTL for each attempt. When the delay expires, RabbitMQ dead-letters the message back to `webhook_delivery_queue`. Consumers never consume retry queues. The same delivery ID is preserved; there are five attempts total (initial attempt 0, retries 1–4), then `webhook_dlq`. A failed retry publish requeues the original delivery.

This is at-least-once processing, not exactly-once delivery. Receivers must deduplicate by delivery ID. Classic queue dead-letter forwarding is not an exactly-once or loss-free guarantee during broker failures; a quorum-queue migration requires separate validation. Do not delete retry queues containing pending messages during deployment.

Use Python 3.12 and `pip install -r requirements-dev.txt`, then `python -m pytest`. Set `TEST_RABBITMQ_URL` only to an isolated test broker/vhost: the integration test purges its delivery and dead-letter queues. CI supplies a disposable broker and checks the real delay and DLQ path. Without the variable, that integration case is skipped.

`requirements.in` and `requirements-dev.in` are direct constraints; their `.txt` files are resolved locks. Regenerate with `uv pip compile requirements.in --python-version 3.12 -o requirements.txt` and the corresponding dev command. Redis and aio-pika remain within their existing major versions.
