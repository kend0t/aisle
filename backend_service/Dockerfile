FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing bytecode and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    AISLE_DATA_SOURCE=firestore

# Install system dependencies if needed (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend service package
COPY . /app/backend_service

# Create non-root user for security
RUN adduser --disabled-password --gecos "" aisleuser \
    && mkdir -p /app/backend_service/temp_uploads \
    && chown -R aisleuser:aisleuser /app

USER aisleuser

EXPOSE 8080

# Cloud Run injects $PORT; uvicorn binds to 0.0.0.0
CMD ["sh", "-c", "uvicorn backend_service.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
