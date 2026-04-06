import os
import torch
import cv2
import numpy as np
from PIL import Image
from torchvision import transforms, models
from ultralytics import YOLO
import json
import random

def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

set_seed(42)

class PizzaInspector:

    def __init__(self, clf_weights="classifier.pth", yolo_weights="yolo_best.pt"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.pizza_classes = {0: "Маргарита", 1: "Пепперони", 2: "Мясная", 3: "Сырная", 4: "Гавайская"}
        self.classifier = models.resnet18(weights=None)
        self.classifier.fc = torch.nn.Linear(self.classifier.fc.in_features, len(self.pizza_classes))
        if os.path.exists(clf_weights):
            self.classifier.load_state_dict(torch.load(clf_weights, map_location=self.device))
            print("Веса классификатора загружены.")
        else:
            print("Файл классификатора не найден! Работает со случайными весами (режим теста).")
        self.classifier.to(self.device)
        self.classifier.eval()

        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        self.yolo = YOLO("yolo_best.pt")

    def _get_pizza_type(self, image_pil):
        img_tensor = self.transform(image_pil).unsqueeze(0).to(self.device)
        with torch.no_grad():
            outputs = self.classifier(img_tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)
            confidence, predicted = torch.max(probabilities, 1)
        return self.pizza_classes[predicted.item()], confidence.item()

    def _analyze_ingredients(self, image_path):

        results = self.yolo(image_path, verbose=False)[0]
        ingredients_count = {}
        if results.boxes is not None:
            for box in results.boxes:
                class_id = int(box.cls)
                class_name = self.yolo.names[class_id]
                ingredients_count[class_name] = ingredients_count.get(class_name, 0) + 1
        return ingredients_count, results

    def inspect_pizza(self, image_path):
        try:
            image_pil = Image.open(image_path).convert('RGB')
            pizza_type, conf = self._get_pizza_type(image_pil)
            ingredients, yolo_data = self._analyze_ingredients(image_path)
            status = "OK"
            reason = "С пиццей все в порядке."
            salami_name = "Pepperoni"

            if pizza_type == "Пепперони":
                salami_count = ingredients.get(salami_name, 0)
                if salami_count < 8:
                    status = "NOT_OK"
                    reason = f"Брак! Найдено всего {salami_count} кусочков колбасы. Должно быть больше 8."

            elif pizza_type == "Сырная":
                if "Pepperoni" in ingredients:
                    status = "NOT_OK"
                    reason = "Брак! В сырной пицце найдены мясные ингредиенты."

            return {
                "success": True,
                "pizza_type": pizza_type,
                "confidence": round(conf, 2),
                "status": status,
                "reason": reason,
                "ingredients_found": ingredients
            }

        except Exception as e:
            return {
                "success": False,
                "status": "ERROR",
                "reason": f"Ошибка обработки изображения: {str(e)}"
            }

if __name__ == "__main__":
    test_image = "test.jpg"
    model = PizzaInspector()
    result = model.inspect_pizza(test_image)
    print(json.dumps(result, indent=4, ensure_ascii=False))
