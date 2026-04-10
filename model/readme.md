Этот модуль отвечает за машинное обучение в проекте. Система построена на базе двухэтапного пайплайна (каскадная архитектура), который сначала находит пиццу на фотографии, а затем классифицирует её.

Модуль разделен на три основных компонента:

PizzaDetector (YOLOv8) — локализует пиццу на исходном фото и возвращает её точные координаты (bounding boxes) вместе с вырезанным фрагментом (crop).

PizzaClassifier (ResNet18) — принимает вырезанный фрагмент лепешки и определяет класс пиццы (Пепперони, Маргарита, Чизбургер и т.д.).

PizzaInspector (Оркестратор) — управляет потоком данных между моделями и формирует итоговый JSON-отчет.

Обучение детектора (YOLO):
Подготовьте датасет в формате YOLO (txt аннотации с одним классом — pizza) и укажите путь к data.yaml.
```
detector = PizzaDetector()
# Порог уверенности, кол-во эпох и путь сохранения можно настроить
detector.train(data_yaml_path="data.yaml", epochs=50, save_path="yolo_pizza_best.pt")
```
Обучение классификатора (ResNet):
Подготовьте датасет, разбитый по папкам с названиями классов (например, dataset/pepperoni/, dataset/margarita/).
```
classifier = PizzaClassifier()
# Модель сама разобьет данные на train/val/test
classifier.train(dataset_dir="dataset", epochs=20, save_path="classifier.pth")
```
Аргумент `save_path` отвечает за путь, по которому сохраняются веса обученной модели.
Модель обучается единожды, для дальнейшей работы используется метод `load_weights`, который загрузит в модель полученные при обучении веса.

Пример работы с моделями:
```
from classifier_model.pizza_classifier import PizzaClassifier
from detection_model.pizza_detector import PizzaDetector
from pizza_inspector import PizzaInspector

# 1. Инициализация
classifier = PizzaClassifier()
detector = PizzaDetector()

# 2. Загрузка весов (пути относительно корня)
classifier.load_weights("classifier_model/classifier.pth")
detector.load_weights("detection_model/yolo_pizza_best.pt")

# 3. Сборка оркестратора
inspector = PizzaInspector(classifier, detector)

# 4. Предикт
result = inspector.inspect_pizza("path/to/test_image.jpg")
print(result)
```
Формат успешного ответа:
```
{
  "success": true,
  "report": "Найдено пицц: 1.",
  "pizzas": [
    {
      "pizza_type": "pepperoni",
      "confidence": 0.95,
      "box": [150, 200, 450, 500]
    }
  ]
}
```
Для демонстрации работы модели можно запустить файл `tester.py`, указав в переменной ` test_dir = "Ваша директория"` путь к директории с тестовыми изображениями.
