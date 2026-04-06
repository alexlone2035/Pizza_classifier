from fastapi import FastAPI, UploadFile, File, requests
from db import save_to_db

app = FastAPI()

ML_API_URL = "http://ml:9000/predict"


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    contents = await file.read()

    # 1. отправка в ML сервис
    response = requests.post(
        ML_API_URL,
        files={"file": ("image.jpg", contents, "image/jpeg")}
    )

    result = response.json()

    # 2. сохранение в БД
    save_to_db(result)

    # 3. возврат результата
    return result