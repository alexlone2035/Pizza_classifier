
class PizzaInspector:
    def __init__(self, classifier, detector):
        self.classifier = classifier
        self.detector = detector

    def inspect_pizza(self, image_path):
        try:
            detected_pizzas = self.detector.detect(image_path)
            if not detected_pizzas:
                return {
                    "success": True,
                    "report": "Пиццы на изображении не найдены.",
                    "pizzas": []
                }

            pizzas_result = []
            for pizza in detected_pizzas:
                pizza_type, conf = self.classifier.predict(pizza["crop"])

                pizzas_result.append({
                    "pizza_type": pizza_type,
                    "confidence": round(conf, 2),
                    "box": pizza["box"]
                })

            return {
                "success": True,
                "report": f"Найдено пицц: {len(pizzas_result)}.",
                "pizzas": pizzas_result
            }
        except Exception as e:
            return {
                "success": False,
                "report": "Ошибка обработки изображения.",
                "reason": str(e),
                "pizzas": []
            }