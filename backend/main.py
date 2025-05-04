from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from PIL import Image
import base64
from io import BytesIO
import requests
import logging
import time
import re

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Kimi API 配置
KIMI_API_KEY = "sk-OFXYS6uoTqKyINHuoPoph6zBQ2yiDHoc4gRBUbNZAB1QdT6J"
KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"

app = FastAPI()

# 挂载静态文件（前端网页）
app.mount("/static", StaticFiles(directory="static"), name="static")

# 允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def call_kimi_api(img_b64, model):
    headers = {
        "Authorization": f"Bearer {KIMI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Kimi, specializing in mathematical tasks. "
                    "Task: Recognize mathematical formulas in the image. "
                    "Output pure LaTeX code only, without \\documentclass, comments, or non-formula content. "
                    "If no formula is detected, return an empty string."
                )
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "Extract the mathematical formula from the image. Return pure LaTeX code."
                    }
                ]
            }
        ],
        "temperature": 0.7
    }

    for attempt in range(4):
        try:
            logger.info(f"Sending Kimi API request, attempt {attempt + 1}/4...")
            response = requests.post(KIMI_API_URL, json=payload, headers=headers, timeout=20)
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After', 15)
                logger.warning(f"Rate limit hit, retry after {retry_after}s")
                time.sleep(float(retry_after))
                continue
            if response.status_code != 200:
                logger.error(f"API request failed with status {response.status_code}: {response.text}")
                raise HTTPException(status_code=500, detail=f"API request failed: {response.status_code} {response.text}")
            result = response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            logger.info(f"Kimi recognition result: {result}")
            # 清理 LaTeX
            result = re.sub(r'\\\[|\\\]', '', result).strip()
            result = re.sub(r'```latex|```', '', result).strip()
            return result
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt + 1}/4 failed: {str(e)}")
            if attempt == 3:
                raise HTTPException(status_code=500, detail=f"API request failed after retries: {str(e)}")
            time.sleep(15)
    raise HTTPException(status_code=429, detail="API rate limit exceeded")

@app.get("/")
async def redirect_to_index():
    logger.info("Serving root path: redirecting to /static/index.html")
    return FileResponse("static/index.html")

@app.get("/{path:path}")
async def serve_spa(path: str):
    logger.info(f"Serving SPA for path: {path}")
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    return FileResponse("static/index.html")

@app.post("/api/recognize")
async def recognize_formula(file: UploadFile = File(...), model: str = Form(...)):
    logger.info(f"Received file: {file.filename}, type: {file.content_type}, size: {file.size}")
    if file.content_type not in ["image/png", "image/jpeg"]:
        raise HTTPException(status_code=400, detail="Invalid file type, only PNG/JPEG allowed")
    if file.size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large, max 5MB")

    try:
        contents = await file.read()
        pil_img = Image.open(BytesIO(contents))
        logger.info(f"Image opened successfully, size: {pil_img.size}, mode: {pil_img.mode}")
    except Exception as e:
        logger.error(f"Failed to open image: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid image: {str(e)}")

    max_width = 800
    if pil_img.width > max_width:
        ratio = max_width / pil_img.width
        new_size = (max_width, int(pil_img.height * ratio))
        pil_img = pil_img.resize(new_size, Image.LANCZOS)

    if pil_img.mode == 'RGBA':
        logger.info("Converting RGBA image to RGB")
        pil_img = pil_img.convert('RGB')

    try:
        buffer = BytesIO()
        pil_img.save(buffer, format="JPEG", quality=90)
        img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to save image as JPEG: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to process image: {str(e)}")

    debug_path = f"debug_screenshot_{int(time.time())}.png"
    pil_img.save(debug_path)
    logger.info(f"Debug image saved: {debug_path}")

    try:
        latex = call_kimi_api(img_b64, model)
        return {"latex": latex, "debug_path": debug_path}
    except Exception as e:
        logger.error(f"Recognition failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
