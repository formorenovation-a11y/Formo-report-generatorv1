FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    poppler-utils \
    xvfb \
    fonts-liberation \
    wget \
    ca-certificates \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && apt-get update && apt-get install -y ./wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && rm wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

RUN mv /usr/local/bin/wkhtmltopdf /usr/local/bin/wkhtmltopdf-real \
    && printf '#!/bin/bash\nxvfb-run -a --server-args="-screen 0 1024x768x24" /usr/local/bin/wkhtmltopdf-real "$@"\n' \
    > /usr/local/bin/wkhtmltopdf \
    && chmod +x /usr/local/bin/wkhtmltopdf

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5000
CMD gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 300 app:app
