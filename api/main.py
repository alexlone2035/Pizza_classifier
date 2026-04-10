from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Form
import httpx
import os
import base64

import db

db.init_db()

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

    try:
        record_id = db.save_to_db(
            {**result, "chat_id": chat_id},
            image_base64
        )
        result["prediction_id"] = record_id
    except Exception as e:
        print("DB error:", e)

    return result



@app.post("/feedback")
async def feedback(
    data: dict,
    authorization: str = Header(None)
):
    if not authorization or authorization != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    prediction_id = data.get("prediction_id")
    verdict = data.get("verdict")

    if not prediction_id:
        raise HTTPException(status_code=400, detail="prediction_id missing")

    db_ = db.SessionLocal()

    try:
        record = db_.query(db.PizzaData).filter(db.PizzaData.id == prediction_id).first()

        if not record:
            raise HTTPException(status_code=404, detail="record not found")

        record.feedback = verdict
        db_.commit()

    finally:
        db_.close()

    return {"status": "ok"}