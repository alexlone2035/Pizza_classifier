from fastapi import FastAPI, UploadFile, File, HTTPException
import shutil
import os
import uuid

from pizza_classifier import PizzaClassifier
from ingredient_detector import IngredientDetector
from pizza_inspector import PizzaInspector

app = FastAPI()

# загрузка моделей при старте
classifier = PizzaClassifier()
detector = IngredientDetector()

classifier.load_weights("classifier.pth")
detector.load_weights("yolo_best.pt")

model = PizzaInspector(classifier, detector)


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Файл должен быть изображением")

    file_id = str(uuid.uuid4())
    file_path = f"/tmp/{file_id}.jpg"

    try:
        # сохраняем файл
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # инференс
        result = model.inspect_pizza(file_path)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # удаляем файл
        if os.path.exists(file_path):
            os.remove(file_path)