from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Form
import httpx
import os
import base64

from db import save_to_db, init_db

init_db()

API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise ValueError("API_KEY not set")

app = FastAPI(title="Pizza API")

ML_API_URL = "http://model:9000/predict"


@app.post("/predict")
async def predict(
    file: UploadFile = File(...),
    chat_id: str = Form(...),
    authorization: str = Header(None)
):
    if not authorization or authorization != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    contents = await file.read()

    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")

    image_base64 = base64.b64encode(contents).decode("utf-8")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                ML_API_URL,
                files={"file": ("image.jpg", contents, "image/jpeg")}
            )
        result = response.json()

    except httpx.RequestError:
        result = {
            "success": False,
            "report": "ML service unavailable",
            "pizzas": []
        }

    # ❌ НЕТ draw_boxes больше

    try:
        record_id = save_to_db(
            {**result, "chat_id": chat_id},
            image_base64
        )
        result["prediction_id"] = record_id
    except Exception as e:
        print("DB error:", e)

    return result