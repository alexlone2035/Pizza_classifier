from PIL import Image

class PizzaInspector:
    def __init__(self, classifier, detector):
        self.classifier = classifier
        self.detector = detector

    def inspect_pizza(self, image_path):
        try:
            image_pil = Image.open(image_path).convert('RGB')
            pizza_type, conf = self.classifier.predict(image_pil)
            ingredients, yolo_data = self.detector.detect(image_path)
            status = "OK"
            reason = "С пиццей все в порядке."

            if pizza_type == "Пепперони":
                salami_count = ingredients.get("Pepperoni", 0)
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
