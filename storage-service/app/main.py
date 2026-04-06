import os
import time
import subprocess
from uuid import uuid4
from typing import List
from playwright.async_api import async_playwright
from fastapi import FastAPI, UploadFile, File, Form
from gtts import gTTS
import requests
from pydantic import BaseModel
from typing import List, Optional

class ReelRequest(BaseModel):
    image_urls: List[str]
    duration_per_slide: int = 2
    audio_url: Optional[str] = None
app = FastAPI()

# ------------------ PATHS ------------------
BASE_PATH = "/data/media"
VIDEO_PATH = os.path.join(BASE_PATH, "videos")
IMAGE_PATH = os.path.join(BASE_PATH, "images")
AUDIO_PATH = os.path.join(BASE_PATH, "audio")
TEMP_PATH = "/tmp"

BASE_URL = os.getenv("BASE_URL", "http://localhost")

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/tmp/playwright"
os.makedirs(VIDEO_PATH, exist_ok=True)
os.makedirs(IMAGE_PATH, exist_ok=True)
os.makedirs(AUDIO_PATH, exist_ok=True)
os.makedirs(TEMP_PATH, exist_ok=True)


def generate_filename(prefix, original_name="file"):
    return f"{prefix}_{uuid4()}_{original_name}"


# ------------------ UPLOAD VIDEO ------------------
@app.post("/upload/video")
async def upload_video(file: UploadFile = File(...)):
    filename = generate_filename("reel", file.filename)
    path = os.path.join(VIDEO_PATH, filename)

    with open(path, "wb") as f:
        f.write(await file.read())

    return {"url": f"{BASE_URL}/media/videos/{filename}"}


# ------------------ UPLOAD IMAGE ------------------
@app.post("/upload/image")
async def upload_image(file: UploadFile = File(...)):
    filename = generate_filename("img", file.filename)

    if not file.filename.lower().endswith((".jpg", ".jpeg", ".png")):
        filename += ".jpg"

    path = os.path.join(IMAGE_PATH, filename)

    with open(path, "wb") as f:
        f.write(await file.read())

    return {"url": f"{BASE_URL}/media/images/{filename}"}


# ------------------ UPLOAD AUDIO ------------------
@app.post("/upload/audio")
async def upload_audio(file: UploadFile = File(...)):
    filename = generate_filename("audio", file.filename)

    if not file.filename.lower().endswith((".mp3", ".wav")):
        filename += ".mp3"

    path = os.path.join(AUDIO_PATH, filename)

    with open(path, "wb") as f:
        f.write(await file.read())

    return {"url": f"{BASE_URL}/media/audio/{filename}"}


# ------------------ TEXT → AUDIO ------------------
@app.post("/generate/audio")
async def generate_audio(text: str = Form(...)):
    try:
        filename = f"audio_{uuid4()}.mp3"
        path = os.path.join(AUDIO_PATH, filename)

        tts = gTTS(text=text)
        tts.save(path)

        return {
            "status": "success",
            "audio_url": f"{BASE_URL}/media/audio/{filename}"
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ------------------ TEXT → SEGMENTS ------------------
def build_tts_segments(title, problem, solution, caption):
    segments = []

    if caption:
        segments.append(caption.split("#")[0].strip())

    if title:
        segments.append(title)

    if problem:
        segments.append(problem[:120])

    if solution:
        segments.append(solution[:120])

    segments.append("Save this and follow for more")

    return segments

@app.post("/generate/image")
async def html_to_image(html: str = Form(...)):
    try:
        filename = f"img_{uuid4()}.png"
        output_path = os.path.join(IMAGE_PATH, filename)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page()

            await page.set_viewport_size({"width": 1080, "height": 1080})

            await page.set_content(html, wait_until="networkidle")

            # 🔥 wait for fonts + rendering
            await page.evaluate("document.fonts.ready")
            await page.wait_for_timeout(1000)

            await page.screenshot(path=output_path)

            await browser.close()

        return {
            "status": "success",
            "image_url": f"{BASE_URL}/media/images/{filename}"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/generate/audio/segments")
async def generate_audio_segments(
    title: str = Form(None),
    problem: str = Form(None),
    solution: str = Form(None),
    caption: str = Form(None)
):
    try:
        segments = build_tts_segments(title, problem, solution, caption)

        audio_files = []
        temp_audio_paths = []
        timestamp = int(time.time())

        # 🔥 Generate audio per segment
        for idx, text in enumerate(segments):
            filename = f"audio_{timestamp}_{idx}.mp3"
            path = os.path.join(AUDIO_PATH, filename)

            tts = gTTS(text=text, lang="en", slow=True)
            tts.save(path)

            audio_files.append(f"{BASE_URL}/media/audio/{filename}")
            temp_audio_paths.append(path)

        # 🔥 Merge audio into single file
        merged_name = f"audio_merged_{timestamp}.mp3"
        merged_path = os.path.join(AUDIO_PATH, merged_name)

        command = ["ffmpeg"]

        for f in temp_audio_paths:
            command.extend(["-i", f])

        command.extend([
            "-filter_complex", f"concat=n={len(temp_audio_paths)}:v=0:a=1",
            "-y",
            merged_path
        ])

        subprocess.run(command, check=True)

        return {
            "status": "success",
            "segments": segments,
            "audio_urls": audio_files,
            "merged_audio_url": f"{BASE_URL}/media/audio/{merged_name}",
            "count": len(segments)
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ------------------ GENERATE REEL ------------------

@app.post("/generate/reel")
async def generate_reel(req: ReelRequest):
    try:
        start = time.time()
        timestamp = int(start)

        image_paths = []

        # ------------------ STEP 1: Download images ------------------
        for idx, url in enumerate(req.image_urls):
            temp_file = os.path.join(TEMP_PATH, f"{timestamp}_{idx}.png")
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            with open(temp_file, "wb") as f:
                f.write(r.content)
            image_paths.append(temp_file)

        # ------------------ STEP 2: Audio handling ------------------
        audio_path = None
        slide_duration = req.duration_per_slide

        if req.audio_url:
            audio_path = os.path.join(
                AUDIO_PATH,
                req.audio_url.split("/")[-1]
            )
            if not os.path.exists(audio_path):
                raise Exception("Audio file not found")

            audio_duration = get_audio_duration(audio_path)
            slide_duration = audio_duration / len(image_paths)

        # ------------------ STEP 3: Build concat file ------------------
        concat_path = os.path.join(TEMP_PATH, f"{timestamp}.txt")

        with open(concat_path, "w") as f:
            for img in image_paths:
                f.write(f"file '{img}'\n")
                f.write(f"duration {slide_duration}\n")
            f.write(f"file '{image_paths[-1]}'\n")

        # ------------------ STEP 4: FFmpeg command ------------------
        output_name = f"reel_{timestamp}.mp4"
        output_path = os.path.join(VIDEO_PATH, output_name)

        filters = (
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
            "format=yuv420p"
        )

        command = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_path
        ]

        if audio_path:
            command.extend(["-i", audio_path])

        command.extend([
            "-vf", filters,
            "-r", "30",
            "-c:v", "libx264",
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-movflags", "+faststart",
            "-shortest",
            output_path
        ])

        subprocess.run(command, check=True)

        # ------------------ STEP 5: Cleanup ------------------
        for p in image_paths:
            os.remove(p)
        os.remove(concat_path)

        return {
            "status": "success",
            "video_url": f"{BASE_URL}/media/videos/{output_name}",
            "slides": len(image_paths),
            "slide_duration": round(slide_duration, 2),
            "audio_enabled": bool(audio_path),
            "processing_time_ms": int((time.time() - start) * 1000)
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_audio_duration(audio_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    result = subprocess.check_output(cmd).decode().strip()
    return float(result)

# ------------------ HEALTH ------------------
@app.get("/health")
def health():
    return {"status": "ok"}
