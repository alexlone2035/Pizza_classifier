from ultralytics import YOLO
import shutil

class IngredientDetector:
    def __init__(self):

        self.yolo = None
        self.weights_path = None

    def load_weights(self, weights_path="yolo_best.pt"):

        self.weights_path = weights_path
        self.yolo = YOLO(self.weights_path)

    def train(self, data_yaml_path="pizza_dataset/data.yaml", epochs=30, save_path="yolo_best.pt"):

        self.yolo = YOLO("yolov8n.pt")
        results = self.yolo.train(
            data=data_yaml_path,
            epochs=epochs,
            imgsz=640,
            batch=16,
            device=0,
            project="pizza_yolo",
            name="train_run"
        )
        best_model_path = str(results.save_dir / "weights" / "best.pt")
        shutil.copy(best_model_path, save_path)
        self.weights_path = save_path
        self.yolo = YOLO(self.weights_path)

    def detect(self, image_path):
        results = self.yolo(image_path, verbose=False)[0]
        ingredients_count = {}

        if results.boxes is not None:
            for box in results.boxes:
                class_id = int(box.cls)
                class_name = self.yolo.names[class_id]
                ingredients_count[class_name] = ingredients_count.get(class_name, 0) + 1

        return ingredients_count, results
