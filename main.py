from fastapi import FastAPI, UploadFile, File
import shutil
import os
import uuid

from model import PizzaInspector  # вынесем класс в model.py

app = FastAPI()

model = PizzaInspector()


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    # создаём временный файл
    file_id = str(uuid.uuid4())
    file_path = f"/tmp/{file_id}.jpg"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # инференс
    result = model.inspect_pizza(file_path)

    # удаляем файл
    os.remove(file_path)

    return result