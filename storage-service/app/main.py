from uuid import uuid4

from fastapi import FastAPI, UploadFile, File
import os
import time

app = FastAPI()

BASE_PATH = "/data/media"
VIDEO_PATH = os.path.join(BASE_PATH, "videos")
IMAGE_PATH = os.path.join(BASE_PATH, "images")
BASE_URL = os.getenv("BASE_URL", "http://localhost")

os.makedirs(VIDEO_PATH, exist_ok=True)
os.makedirs(IMAGE_PATH, exist_ok=True)


def generate_filename(prefix, original_name):
    return f"{prefix}_{uuid4()}_{original_name}"


@app.post("/upload/video")
async def upload_video(file: UploadFile = File(...)):
    filename = generate_filename("reel", file.filename)
    file_path = os.path.join(VIDEO_PATH, filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    return {
        "url": f"{BASE_URL}/media/videos/{filename}"
    }


@app.post("/upload/image")
async def upload_image(file: UploadFile = File(...)):
    filename = generate_filename("img", file.filename)
    if not (file.filename.endswith(".jpg") or file.filename.endswith(".jpeg") or file.filename.endswith(".png")):
        filename+= ".jpg"  # Default to .jpg if no valid extension provided
    file_path = os.path.join(IMAGE_PATH, filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    return {
        "url": f"{BASE_URL}/media/images/{filename}"
    }


@app.get("/health")
def health():
    return {"status": "ok"}