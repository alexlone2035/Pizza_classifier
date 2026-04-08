from fastapi import FastAPI, UploadFile, File, Header, HTTPException
import requests
from db import save_to_db
import os

API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise ValueError("API_KEY not set")

app = FastAPI()

ML_API_URL = "http://ml:9000/predict"


@app.post("/predict")
async def predict(
    file: UploadFile = File(...),
    authorization: str = Header(None)
):
    if not authorization or authorization != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    contents = await file.read()

    try:
        response = requests.post(
            ML_API_URL,
            files={"file": ("image.jpg", contents, "image/jpeg")},
            timeout=10
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"ML service error: {response.status_code}"
            )

        result = response.json()

    except requests.exceptions.RequestException:
        raise HTTPException(
            status_code=500,
            detail="ML service unavailable"
        )

    try:
        save_to_db(result)
    except Exception as e:
        print("DB error:", e)

    return result
