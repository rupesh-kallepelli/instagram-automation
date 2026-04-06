import os
import time
import subprocess
import asyncio
import requests

from uuid import uuid4
from typing import List
from playwright.async_api import async_playwright
from fastapi import FastAPI, UploadFile, File, Form
from gtts import gTTS
from pydantic import BaseModel
from typing import List, Optional

class ReelRequest(BaseModel):
    image_urls: List[str]
    duration_per_slide: int = 2
    audio_url: Optional[str] = None

class ClipRequest(BaseModel):
    image_url: str
    audio_urls: List[str]

class MergeClipsRequest(BaseModel):
    clip_urls: List[str]
    
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
        filename = f"audio_{uuid4()}.wav"
        path = os.path.join(AUDIO_PATH, filename)

        generate_tts_piper(text, path)

        return {
            "status": "success",
            "audio_url": f"{BASE_URL}/media/audio/{filename}"
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

def generate_tts_piper(text: str, output_path: str):
    """
    Generate speech using Piper TTS (offline, CPU-only, male voice)
    """
    subprocess.run(
        [
            "piper",
            "--model", "en_US-hfc_male-medium",
            "--output_file", output_path
        ],
        input=text.encode("utf-8"),
        check=True
    )
# ------------------ TEXT → SEGMENTS ------------------
def build_tts_segments(title, problem, solution, caption):
    segments = []

    if caption:
        segments.append(caption.split("#")[0].strip())

    if title:
        segments.append(title)

    if problem:
        segments.append(problem)

    if solution:
        segments.append(solution)

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

        # ✅ Generate audio per segment using Piper
        for idx, text in enumerate(segments):
            filename = f"audio_{timestamp}_{idx}.wav"
            path = os.path.join(AUDIO_PATH, filename)

            generate_tts_piper(text, path)

            audio_files.append(f"{BASE_URL}/media/audio/{filename}")
            temp_audio_paths.append(path)

        # ✅ Merge audio
        merged_name = f"audio_merged_{timestamp}.wav"
        merged_path = os.path.join(AUDIO_PATH, merged_name)

        concat_file = os.path.join(TEMP_PATH, f"audio_concat_{timestamp}.txt")
        with open(concat_file, "w") as f:
            for p in temp_audio_paths:
                f.write(f"file '{p}'\n")

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_file,
                "-filter:a", "atempo=1.15",   # ✅ medium voice speed
                merged_path
            ],
            check=True
        )

        os.remove(concat_file)

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
    start = time.time()
    timestamp = int(start)
    image_paths = []

    try:
        # ------------------ STEP 1: Download images (STREAMED) ------------------
        for idx, url in enumerate(req.image_urls):
            temp_file = os.path.join(TEMP_PATH, f"{timestamp}_{idx}.png")

            r = requests.get(url, stream=True, timeout=15)
            r.raise_for_status()

            with open(temp_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            image_paths.append(temp_file)

        if not image_paths:
            raise Exception("No images downloaded")

        # ------------------ STEP 2: Audio handling ------------------
        audio_path = None
        slide_duration = float(req.duration_per_slide)

        if req.audio_url:
            audio_path = os.path.join(
                AUDIO_PATH,
                req.audio_url.split("/")[-1]
            )

            if not os.path.isfile(audio_path):
                raise Exception(f"Audio file not found: {audio_path}")

            audio_duration = get_audio_duration(audio_path)
            slide_duration = audio_duration / len(image_paths)

        # ------------------ STEP 3: Build concat file ------------------
        concat_path = os.path.join(TEMP_PATH, f"{timestamp}.txt")

        with open(concat_path, "w") as f:
            for img in image_paths:
                f.write(f"file '{img}'\n")
                f.write(f"duration {slide_duration}\n")
            f.write(f"file '{image_paths[-1]}'\n")

        # ------------------ STEP 4: Prepare FFmpeg command ------------------
        output_name = f"reel_{timestamp}.mp4"
        output_path = os.path.join(VIDEO_PATH, output_name)

        video_filter = (
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
            "format=yuv420p"
        )

        command = [
            "ffmpeg",
            "-loglevel", "error",      # ✅ suppress noisy logs
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_path
        ]

        if audio_path:
            command.extend(["-i", audio_path])

        command.extend([
            "-vf", video_filter,
            "-r", "30",
            "-c:v", "libx264",
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-movflags", "+faststart",
            "-shortest",
            output_path
        ])

        # ------------------ STEP 5: Run FFmpeg SAFELY (NON‑BLOCKING) ------------------
        result = await asyncio.to_thread(
            subprocess.run,
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        if result.returncode != 0:
            raise Exception(result.stderr.decode() or "FFmpeg failed")

        # ------------------ STEP 6: Cleanup ------------------
        for p in image_paths:
            if os.path.exists(p):
                os.remove(p)

        if os.path.exists(concat_path):
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
        # ✅ Cleanup even on failure
        for p in image_paths:
            if os.path.exists(p):
                os.remove(p)
        return {
            "status": "error",
            "message": str(e)
        }

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

def download_file(url: str, path: str):
    r = requests.get(url, stream=True, timeout=20)
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)
                
def merge_and_speed_audio(audio_paths: List[str], output_audio: str):
    list_file = output_audio.replace(".mp3", ".txt")

    with open(list_file, "w") as f:
        for a in audio_paths:
            f.write(f"file '{a}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-filter:a", "atempo=1.15",  # ✅ medium speed
        "-c:a", "mp3",
        output_audio
    ]

    subprocess.run(cmd, check=True)
    os.remove(list_file)

def image_audio_to_video(image_path: str, audio_path: str, output_path: str):
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
        "format=yuv420p",
        "-c:v", "libx264",
        "-preset", "ultrafast",  # ✅ fast → avoids 504
        "-c:a", "aac",
        "-shortest",
        output_path
    ]

    subprocess.run(cmd, check=True)

@app.post("/generate/clip")
async def generate_clip(req: ClipRequest):
    ts = int(time.time())

    image_path = f"{TEMP_PATH}/img_{ts}.png"
    audio_paths = []
    merged_audio = f"{TEMP_PATH}/audio_{ts}.mp3"
    output_video = f"{VIDEO_PATH}/clip_{ts}.mp4"

    try:
        # 1️⃣ Download image
        download_file(req.image_url, image_path)

        # 2️⃣ Download audios
        for i, url in enumerate(req.audio_urls):
            ap = f"{TEMP_PATH}/a_{ts}_{i}.mp3"
            download_file(url, ap)
            audio_paths.append(ap)

        # 3️⃣ Merge + speed‑fix audio
        merge_and_speed_audio(audio_paths, merged_audio)

        # 4️⃣ Image + audio → video
        image_audio_to_video(image_path, merged_audio, output_video)

        return {
            "status": "success",
            "video_url": f"{BASE_URL}/media/videos/clip_{ts}.mp4"
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/merge/clips")
async def merge_clips(req: MergeClipsRequest):
    ts = int(time.time())
    local_clips = []

    try:
        # 1️⃣ Download clips in order
        for i, url in enumerate(req.clip_urls):
            path = f"{TEMP_PATH}/clip_{ts}_{i}.mp4"
            download_file(url, path)
            local_clips.append(path)

        # 2️⃣ Build concat file
        concat_file = f"{TEMP_PATH}/concat_{ts}.txt"
        with open(concat_file, "w") as f:
            for c in local_clips:
                f.write(f"file '{c}'\n")

        # 3️⃣ Merge (NO re‑encode → fast)
        output_video = f"{VIDEO_PATH}/reel_{ts}.mp4"
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_video
        ], check=True)

        return {
            "status": "success",
            "video_url": f"{BASE_URL}/media/videos/reel_{ts}.mp4"
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ------------------ HEALTH ------------------
@app.get("/health")
def health():
    return {"status": "ok"}
