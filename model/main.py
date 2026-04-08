from fastapi import FastAPI, UploadFile, File, HTTPException
from PIL import Image
import io
import logging

from pizza_classifier import PizzaClassifier
from ingredient_detector import IngredientDetector
from pizza_inspector import PizzaInspector

# логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# 🔥 загрузка моделей один раз
classifier = PizzaClassifier()
detector = IngredientDetector()

classifier.load_weights("classifier.pth")
detector.load_weights("yolo_best.pt")

model = PizzaInspector(classifier, detector)


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    # проверка типа
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Файл должен быть изображением")

    try:
        contents = await file.read()

        # ⚠️ ограничение размера (5MB)
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Файл слишком большой")

        # 📸 открываем изображение в памяти
        # 🚀 инференс
        result = model.inspect_pizza(contents)

        logger.info(f"Prediction: {result}")

        return result

    except Exception as e:
        logger.error(f"Ошибка инференса: {e}")
        raise HTTPException(status_code=500, detail=str(e))
