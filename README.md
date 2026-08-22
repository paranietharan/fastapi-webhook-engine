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