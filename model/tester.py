import unittest
from unittest.mock import MagicMock, patch
from pizza_inspector import PizzaInspector


class TestPizzaInspector(unittest.TestCase):
    def setUp(self):
        # Эта функция запускается перед каждым тестом.
        # Создаем "заглушки" для моделей, чтобы не грузить реальные веса
        self.mock_classifier = MagicMock()
        self.mock_detector = MagicMock()
        self.inspector = PizzaInspector(self.mock_classifier, self.mock_detector)

    # @patch подменяет функцию Image.open, чтобы тестам не нужны были реальные картинки
    @patch('pizza_inspector.Image.open')
    def test_1_cheese_pizza_clean(self, mock_image_open):
        """Сырная пицца без мяса -> статус OK"""
        self.mock_classifier.predict.return_value = ("syrnaya", 0.99)
        self.mock_detector.detect.return_value = ({"Cheese": 5, "Tomato": 3}, [])

        result = self.inspector.inspect_pizza("dummy.jpg")
        self.assertEqual(result["status"], "OK")

    @patch('pizza_inspector.Image.open')
    def test_2_cheese_pizza_with_meat(self, mock_image_open):
        """Сырная пицца, в которой найдено мясо -> статус NOT_OK"""
        self.mock_classifier.predict.return_value = ("syrnaya", 0.99)
        self.mock_detector.detect.return_value = ({"Pepperoni": 1}, [])

        result = self.inspector.inspect_pizza("dummy.jpg")
        self.assertEqual(result["status"], "NOT_OK")
        self.assertIn("pepperoni", result["reason"])

    @patch('pizza_inspector.Image.open')
    def test_3_standard_pizza_clean(self, mock_image_open):
        """Маргарита (нужны только томаты), мяса нет -> статус OK"""
        self.mock_classifier.predict.return_value = ("margarita", 0.95)
        self.mock_detector.detect.return_value = ({"Tomato": 10}, [])

        result = self.inspector.inspect_pizza("dummy.jpg")
        self.assertEqual(result["status"], "OK")

    @patch('pizza_inspector.Image.open')
    def test_4_standard_pizza_foreign_meat_fails(self, mock_image_open):
        """Маргарита, но детектор нашел 2 куска курицы -> статус NOT_OK"""
        self.mock_classifier.predict.return_value = ("margarita", 0.95)
        self.mock_detector.detect.return_value = ({"Chicken": 2}, [])

        result = self.inspector.inspect_pizza("dummy.jpg")
        self.assertEqual(result["status"], "NOT_OK")
        self.assertIn("chicken", result["reason"])

    @patch('pizza_inspector.Image.open')
    def test_5_standard_pizza_hallucination_ok(self, mock_image_open):
        """Маргарита, детектор нашел 1 бекон. Прощаем глюк YOLO (<=1) -> статус OK"""
        self.mock_classifier.predict.return_value = ("margarita", 0.95)
        self.mock_detector.detect.return_value = ({"Bacon": 1}, [])

        result = self.inspector.inspect_pizza("dummy.jpg")
        self.assertEqual(result["status"], "OK")

    @patch('pizza_inspector.Image.open')
    def test_6_standard_pizza_allowed_meat_ok(self, mock_image_open):
        """Мясная пицца, нашли разрешенное мясо (пепперони и бекон) -> статус OK"""
        self.mock_classifier.predict.return_value = ("myasnaya", 0.90)
        self.mock_detector.detect.return_value = ({"Pepperoni": 15, "Bacon": 10}, [])

        result = self.inspector.inspect_pizza("dummy.jpg")
        self.assertEqual(result["status"], "OK")

    @patch('pizza_inspector.Image.open')
    def test_7_mix_pizza_always_ok(self, mock_image_open):
        """Пицца из категории 'any' (Папа Микс) пропускает любые ингредиенты -> статус OK"""
        self.mock_classifier.predict.return_value = ("papamiks", 0.85)
        self.mock_detector.detect.return_value = ({"Pepperoni": 5, "Chicken": 5}, [])

        result = self.inspector.inspect_pizza("dummy.jpg")
        self.assertEqual(result["status"], "OK")

    @patch('pizza_inspector.Image.open')
    def test_8_unknown_pizza_defaults_to_any(self, mock_image_open):
        """Неизвестная пицца обрабатывается по правилу 'any' -> статус OK"""
        self.mock_classifier.predict.return_value = ("unknown_new_pizza", 0.80)
        self.mock_detector.detect.return_value = ({"Ham": 2}, [])

        result = self.inspector.inspect_pizza("dummy.jpg")
        self.assertEqual(result["status"], "OK")

    @patch('pizza_inspector.Image.open')
    def test_9_classifier_exception(self, mock_image_open):
        """Имитация падения классификатора -> перехват ошибки и статус ERROR"""
        self.mock_classifier.predict.side_effect = Exception("Model died")

        result = self.inspector.inspect_pizza("dummy.jpg")
        self.assertEqual(result["success"], False)
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("Model died", result["reason"])

    @patch('pizza_inspector.Image.open')
    def test_10_detector_exception(self, mock_image_open):
        """Имитация падения детектора YOLO -> перехват ошибки и статус ERROR"""
        self.mock_classifier.predict.return_value = ("pepperoni", 0.99)
        self.mock_detector.detect.side_effect = Exception("YOLO exploded")

        result = self.inspector.inspect_pizza("dummy.jpg")
        self.assertEqual(result["success"], False)
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("YOLO exploded", result["reason"])


if __name__ == '__main__':
    unittest.main()