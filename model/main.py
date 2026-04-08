from fastapi import FastAPI, UploadFile, File
import os
import shutil
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
async def predict_pizza(file: UploadFile = File(...)):
    # 1. Генерируем имя для временного файла
    temp_image_path = f"temp_{file.filename}"

    try:
        # 2. Физически сохраняем присланную картинку на диск внутри Докера
        with open(temp_image_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 3. Передаем ПУТЬ к сохраненному файлу в наш инспектор (как он и просит)
        result = model.inspect_pizza(temp_image_path)
        return result

    except Exception as e:
        return {"success": False, "status": "ERROR", "reason": f"Ошибка: {str(e)}"}

    finally:
        # 4. ОБЯЗАТЕЛЬНО удаляем временный файл, чтобы жесткий диск Докера не переполнился
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)
