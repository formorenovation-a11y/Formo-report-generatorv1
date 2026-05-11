FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    poppler-utils \
    fonts-liberation \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5000
CMD gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 300 app:app
