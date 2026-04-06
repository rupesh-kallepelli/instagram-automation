FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 🔥 FIX: set playwright path
ENV PLAYWRIGHT_BROWSERS_PATH=/tmp/playwright

# Install dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    wget \
    gnupg \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libxshmfence1 \
    libgtk-3-0 \
    fonts-noto-color-emoji \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && playwright install chromium

COPY app/ .

RUN mkdir -p /data/media/videos /data/media/images /data/media/audio /tmp/playwright

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]