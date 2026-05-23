FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y \
    git curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY backend/ ./backend/

# Copy frontend (served by FastAPI as static files)
COPY frontend/ ./frontend/

# Patch main.py to serve static files
RUN echo "
from fastapi.staticfiles import StaticFiles
import os, sys
sys.path.insert(0, '/app/backend')
" >> /dev/null

WORKDIR /app/backend

EXPOSE 8080

# Start FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
