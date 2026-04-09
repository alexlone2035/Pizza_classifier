from ultralytics import YOLO
import shutil
from PIL import Image

class PizzaDetector:
    def __init__(self):
        self.yolo = None
        self.weights_path = None

    def load_weights(self, weights_path="yolo_pizza_best.pt"):
        self.weights_path = weights_path
        self.yolo = YOLO(self.weights_path)

    def train(self, data_yaml_path, epochs=30, save_path="yolo_best.pt"):
        self.yolo = YOLO("yolov8n.pt")
        results = self.yolo.train(
            data=data_yaml_path,
            epochs=epochs,
            imgsz=640,
            batch=16,
            device=0,
            project="pizza_yolo_run",
            name="train_run"
        )

        metrics = self.yolo.val()
        print(f"Точность детектора (mAP50): {metrics.results_dict['metrics/mprecision(B)']:.4f}")

        best_model_path = str(results.save_dir / "weights" / "best.pt")
        shutil.copy(best_model_path, save_path)
        self.weights_path = save_path
        self.yolo = YOLO(self.weights_path)
        print(f"Обучение детектора завершено. Веса сохранены: {save_path}")

    def detect(self, image_path):

        results = self.yolo(image_path, verbose=False)[0]
        original_image = Image.open(image_path).convert("RGB")

        pizzas_data = []

        if results.boxes is not None:
            for box in results.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = box.conf[0].item()
                crop = original_image.crop((x1, y1, x2, y2))

                pizzas_data.append({
                    "box": [int(x1), int(y1), int(x2), int(y2)],
                    "crop": crop,
                    "detection_conf": conf
                })

        return pizzas_data