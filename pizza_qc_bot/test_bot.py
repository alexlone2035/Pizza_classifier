import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import bot  # Импортируем твой файл bot.py


class TestPizzaBot(unittest.IsolatedAsyncioTestCase):

    # --- 1. ТЕСТ ЛОГИКИ ФОРМАТИРОВАНИЯ ---
    def test_format_response_success(self):
        """Проверяем сборку сообщения из нескольких объектов"""
        api_data = {
            "success": True,
            "report": "Найдено объектов: 2",
            "pizzas": [
                {"pizza_type": "pepperoni", "confidence": 0.98, "box": [10, 20, 100, 200]},
                {"pizza_type": "margarita", "confidence": 0.85, "box": [300, 400, 500, 600]}
            ]
        }

        result = bot.format_response(api_data)

        self.assertIn("📊 *Найдено объектов: 2*", result)
        self.assertIn("🍕 *Объект #1: Pepperoni*", result)
        self.assertIn("🎯 Уверенность: 98.0%", result)
        self.assertIn("📍 Координаты (box): `[10, 20, 100, 200]`", result)

    def test_format_response_error(self):
        """Проверяем вывод при ошибке от API"""
        api_data = {"success": False, "reason": "Server Overloaded"}
        result = bot.format_response(api_data)
        self.assertIn("❌ Ошибка", result)

    # --- 2. ТЕСТ ОТПРАВКИ В API МОДЕЛИ ---
    @patch("aiohttp.ClientSession.post")
    async def test_send_to_model_api(self, mock_post):
        """Имитируем запрос к API сокомандника"""
        # Настраиваем мок ответа
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json.return_value = {"success": True, "pizzas": []}
        mock_post.return_value.__aenter__.return_value = mock_resp

        result = await bot.send_to_model_api(b"fake_image", 123456)

        self.assertTrue(result["success"])
        mock_post.assert_called_once()

    # --- 3. ТЕСТ ОБРАБОТКИ ФИДБЕКА ---
    @patch("aiohttp.ClientSession.post")
    async def test_handle_feedback(self, mock_post):
        """Проверяем, что фидбек помечается как отданный"""
        # Создаем фальшивый callback query
        query = AsyncMock()
        query.data = "fb:correct:999"

        update = MagicMock()
        update.callback_query = query

        # Забиваем тестовую сессию
        bot.user_sessions[999] = {
            "api_result": {"pizzas": []},
            "feedback_given": False
        }

        # Мокаем успешную отправку фидбека в API
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_post.return_value.__aenter__.return_value = mock_resp

        await bot.handle_feedback(update, AsyncMock())

        # Проверяем результат
        self.assertTrue(bot.user_sessions[999]["feedback_given"])
        query.edit_message_reply_markup.assert_called_once()
        query.message.reply_text.assert_called_with("🙏 Спасибо за отзыв!")


if __name__ == "__main__":
    unittest.main()
