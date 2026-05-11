FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    wkhtmltopdf \
    fonts-liberation \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# wkhtmltopdf needs a display - wrap it
RUN echo '#!/bin/bash\nxvfb-run -a --server-args="-screen 0 1024x768x24" /usr/bin/wkhtmltopdf "$@"' \
    > /usr/local/bin/wkhtmltopdf && chmod +x /usr/local/bin/wkhtmltopdf

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 300 app:app
