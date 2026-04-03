from fastapi import FastAPI
from pydantic import BaseModel
from diffusers import StableDiffusionXLPipeline
import torch
from io import BytesIO
import base64

app = FastAPI()

device = "cuda" if torch.cuda.is_available() else "cpu"

pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    torch_dtype=torch.float16 if device == "cuda" else torch.float32
).to(device)

class Request(BaseModel):
    prompt: str

@app.post("/generate")
def generate(req: Request):
    image = pipe(req.prompt, num_inference_steps=25).images[0]

    buffer = BytesIO()
    image.save(buffer, format="PNG")

    return {
        "image": base64.b64encode(buffer.getvalue()).decode()
    }