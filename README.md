```bash

# Create a virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install your dependencies
pip install -r requirements.txt

# Run your server
uvicorn main:app --reload
```

## DB Migrations

```bash
alembic init -t async migrations
```

configure it if not
```bash
# migrations/env.py

# 1. Import your Base model and any other models so they register with Base
from app.models.webhook import Base # Make sure to import all your models!

# 2. Assign the metadata to target_metadata
target_metadata = Base.metadata
```

```bash
alembic revision --autogenerate -m "create_webhook_tables"
```

```bash
alembic upgrade head
```