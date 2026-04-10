import pytest
import os
from PIL import Image

from Classifier_model.pizza_classifier import PizzaClassifier
from Detection_model.pizza_detector import PizzaDetector
from pizza_inspector import PizzaInspector

# --- НАСТРОЙКИ ПУТЕЙ ---
# Убедись, что эти пути совпадают с твоей структурой папок
TEST_IMAGE_PATH = "test.jpg"
CLASSIFIER_WEIGHTS = "Model/Classifier_model/classifier.pth"  # или "classifier_model/classifier.pth"
DETECTOR_WEIGHTS = "Model/Detection_model/yolo_best.pt"  # или "detection_model/yolo_pizza_best.pt"


# ==========================================
# ФИКСТУРЫ (Подготовка окружения)
# ==========================================

@pytest.fixture(scope="module")
def check_files():
    """Проверяем, что все нужные файлы существуют, чтобы тест не падал с непонятной ошибкой"""
    assert os.path.exists(TEST_IMAGE_PATH), f"❌ Тестовое фото не найдено: {TEST_IMAGE_PATH}"
    assert os.path.exists(CLASSIFIER_WEIGHTS), f"❌ Веса классификатора не найдены: {CLASSIFIER_WEIGHTS}"
    assert os.path.exists(DETECTOR_WEIGHTS), f"❌ Веса детектора не найдены: {DETECTOR_WEIGHTS}"


@pytest.fixture(scope="module")
def pipeline(check_files):
    """
    Загружаем тяжелые модели ОДИН РАЗ для всех тестов (scope="module").
    Это экономит кучу времени при запуске тестов.
    """
    classifier = PizzaClassifier()
    classifier.load_weights(CLASSIFIER_WEIGHTS)

    detector = PizzaDetector()
    detector.load_weights(DETECTOR_WEIGHTS)

    inspector = PizzaInspector(classifier, detector)

    return {
        "classifier": classifier,
        "detector": detector,
        "inspector": inspector
    }


# ==========================================
# САМИ ТЕСТЫ
# ==========================================

def test_detector_works(pipeline):
    """Тестируем класс PizzaDetector"""
    detector = pipeline["detector"]

    # Делаем предикт на реальном фото
    results = detector.detect(TEST_IMAGE_PATH)

    # Проверяем, что вернулся список
    assert isinstance(results, list), "Детектор должен возвращать список (list)"

    # Если на тестовом фото есть хотя бы 1 пицца, проверяем структуру данных
    if len(results) > 0:
        first_pizza = results[0]
        assert "box" in first_pizza, "В ответе детектора нет координат (box)"
        assert "crop" in first_pizza, "В ответе детектора нет обрезанного фото (crop)"
        assert "detection_conf" in first_pizza, "В ответе нет уверенности (detection_conf)"

        # Проверяем, что crop - это реально картинка, которую можно передать дальше
        assert isinstance(first_pizza["crop"], Image.Image), "Кроп должен быть объектом PIL.Image"
        assert len(first_pizza["box"]) == 4, "Бокс должен состоять из 4 координат"


def test_classifier_works(pipeline):
    """Тестируем класс PizzaClassifier"""
    classifier = pipeline["classifier"]

    # Для теста классификатора просто откроем наше фото напрямую
    # (даже если там не вырезанная пицца, модель должна выдать какой-то прогноз)
    test_image_pil = Image.open(TEST_IMAGE_PATH).convert("RGB")

    pizza_type, confidence = classifier.predict(test_image_pil)

    # Проверяем типы возвращаемых данных
    assert isinstance(pizza_type, str), "Класс пиццы должен быть строкой"
    assert isinstance(confidence, float), "Уверенность (confidence) должна быть числом (float)"
    assert 0.0 <= confidence <= 1.0, "Уверенность должна быть в диапазоне от 0 до 1"


def test_inspector_works(pipeline):
    """Тестируем класс PizzaInspector (Оркестратор всего пайплайна)"""
    inspector = pipeline["inspector"]

    # Запускаем полный цикл
    result = inspector.inspect_pizza(TEST_IMAGE_PATH)

    # Проверяем формат итогового JSON (словаря)
    assert isinstance(result, dict), "Инспектор должен возвращать словарь (JSON)"
    assert "success" in result, "В ответе нет статуса success"
    assert "report" in result, "В ответе нет текстового отчета report"
    assert "pizzas" in result, "В ответе нет массива pizzas"

    # Проверяем, что если произошла ошибка, success будет False (в норме должен быть True)
    assert result["success"] is True, f"Инспектор упал с ошибкой: {result.get('reason', 'Неизвестная ошибка')}"

    # Если пиццы найдены, проверяем формат итоговой выдачи
    if len(result["pizzas"]) > 0:
        pizza_info = result["pizzas"][0]
        assert "pizza_type" in pizza_info
        assert "confidence" in pizza_info
        assert "box" in pizza_info