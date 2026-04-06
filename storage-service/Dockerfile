FROM python:3.11-slim

# 🔥 Prevent Python buffering issues
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 🔥 Install system dependencies (FFmpeg + basic libs)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 🔥 Copy requirements first (for caching)
COPY app/requirements.txt .

# 🔥 Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 🔥 Copy app code
COPY app/ .

# 🔥 Create required directories (important for OCP)
RUN mkdir -p /data/media/videos /data/media/images /data/media/audio /tmp

# 🔥 Expose port
EXPOSE 8000

# 🔥 Run app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]