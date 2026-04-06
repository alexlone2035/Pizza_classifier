from ultralytics import YOLO

def main():
    print("🤖 Загрузка базовой модели YOLOv8...")
    model = YOLO("yolov8n.pt")
    model.train(
        data="pizza_dataset/data.yaml",
        epochs=30,
        imgsz=640,
        batch=16,
        device=0,
        name="pizza_run"
    )
    print("✅ Обучение завершено!")

if __name__ == "__main__":
    main()