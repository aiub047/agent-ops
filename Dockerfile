FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source (agent definitions are baked in;
# override with a ConfigMap volume mount for frequent changes)
COPY app/ ./app/
COPY agent-definition/ ./agent-definition/
COPY main.py .

ENV APP_ENV=prod \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
