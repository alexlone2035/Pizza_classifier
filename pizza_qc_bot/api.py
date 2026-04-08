import os
import uuid
from fastapi import FastAPI, File, UploadFile, Header, HTTPException
from inspector import PizzaInspector

app = FastAPI(title="Pizza Inspection API")

# Инициализируем модель здесь (как вы и просили)
# Если в будущем будет несколько файлов, инициализируйте их здесь же
inspector = PizzaInspector(clf_weights="classifier.pth", yolo_weights="yolo_best.pt")

# Простая проверка ключа (API_KEY)
API_KEY = os.getenv("API_KEY", "default_secret_key")


@app.post("/predict")
async def predict(
        file: UploadFile = File(...),
        authorization: str = Header(None)
):
    # Проверка авторизации (Bearer token)
    if not authorization or authorization != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 1. Создаем уникальное имя и сохраняем файл
    file_extension = file.filename.split(".")[-1]
    temp_filename = f"api_temp_{uuid.uuid4()}.{file_extension}"

    with open(temp_filename, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    try:
        # 2. Просим инспектора проверить пиццу
        result = inspector.inspect_pizza(temp_filename)
        return result

    except Exception as e:
        return {"success": False, "reason": str(e)}

    finally:
        # 3. Удаляем временный файл
        if os.path.exists(temp_filename):
            os.remove(temp_filename)


@app.post("/feedback")
async def feedback(data: dict):
    # Здесь можно реализовать логику сохранения отзывов в базу данных
    print(f"Получен фидбек: {data}")
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    # Запуск сервера на порту 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
