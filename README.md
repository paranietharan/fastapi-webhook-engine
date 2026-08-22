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