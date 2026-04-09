import os
import logging
import aiohttp
import io
from PIL import Image, ImageDraw
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")

if not TELEGRAM_TOKEN or not API_BASE_URL or not API_KEY:
    raise ValueError("Check env variables")

PREDICT_URL = f"{API_BASE_URL}/predict"
FEEDBACK_URL = f"{API_BASE_URL}/feedback"

user_sessions: dict = {}


def draw_bounding_boxes(image_bytes: bytes, pizzas: list) -> bytes:
    """Рисует цветные bounding boxes на изображении"""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    W, H = img.size

    TYPE_COLORS = {
        "pepperoni": "#FF3333",
        "margarita": "#FF8800",
        "four_cheese": "#FFD700",
        "unknown": "#888888",
    }

    for pizza in pizzas:
        box = pizza.get("box")
        if not box or len(box) != 4:
            continue

        x_min, y_min, x_max, y_max = box
        pizza_type = pizza.get("pizza_type", "unknown")
        color = TYPE_COLORS.get(pizza_type, TYPE_COLORS["unknown"])

        # Рисуем рамку
        draw.rectangle([x_min, y_min, x_max, y_max], outline=color, width=5)

        # Текст (Тип и уверенность)
        conf = pizza.get("confidence", 0) * 100
        label = f"{pizza_type.capitalize()} ({conf:.0f}%)"
        label_y = max(y_min - 25, 0)
        # Фон под текст для читаемости
        draw.rectangle([x_min, label_y, x_min + len(label) * 9, label_y + 20], fill=color)
        draw.text((x_min + 5, label_y + 2), label, fill="white")

    output = io.BytesIO()
    img.save(output, format="JPEG", quality=90)
    return output.getvalue()

async def send_to_model_api(image_bytes: bytes, user_id: int) -> dict:
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with aiohttp.ClientSession() as session:
        form = aiohttp.FormData()
        form.add_field(
            "file",
            image_bytes,
            filename="pizza.jpg",
            content_type="image/jpeg"
        )
        form.add_field("chat_id", str(user_id))

        try:
            async with session.post(
                    PREDICT_URL,
                    data=form,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return {"success": False, "reason": f"Ошибка сервера: {resp.status}"}
        except Exception as e:
            return {"success": False, "reason": f"Ошибка соединения: {str(e)}"}


# --- ОБНОВЛЕННЫЙ FORMAT_RESPONSE ---
def format_response(api_result: dict, image_bytes: bytes = None) -> tuple:
    """
    Возвращает кортеж: (строка_текста, байты_изображения)
    """
    # 1. Обработка ошибки сервера
    if not api_result.get("success"):
        reason = api_result.get("reason", "Сервер не смог обработать изображение.")
        return f"❌ Ошибка: {reason}", None

    # 2. Формируем текстовый отчет
    report = api_result.get("report", "Обработка завершена")
    lines = [f"📊 *{report}*", ""]
    pizzas = api_result.get("pizzas", [])

    if not pizzas:
        lines.append("Пиццы на фото не найдены.")
        # Если пицц нет, возвращаем оригинальное фото (или None, если байты не пришли)
        processed_image = image_bytes
    else:
        for i, pizza in enumerate(pizzas, 1):
            p_type = pizza.get("pizza_type", "unknown")
            conf = pizza.get("confidence", 0) * 100
            lines.append(f"🍕 *Объект #{i}: {p_type.capitalize()}* ({conf:.1f}%)")

        # 3. Пытаемся отрисовать боксы
        if image_bytes:
            try:
                processed_image = draw_bounding_boxes(image_bytes, pizzas)
            except Exception as e:
                logger.error(f"Ошибка при отрисовке боксов: {e}")
                # Если рисование упало, возвращаем хотя бы оригинал
                processed_image = image_bytes
        else:
            processed_image = None

    return "\n".join(lines), processed_image



async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Пришли фото пиццы, и я определю её вид.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = await update.message.reply_text("⏳ Нейросеть думает...")

    # 1. Получаем фото и переводим в байты
    photo_file = await update.message.photo[-1].get_file()
    async with aiohttp.ClientSession() as session:
        async with session.get(photo_file.file_path) as resp:
            image_bytes = await resp.read()

    # 2. Запрос к API
    api_result = await send_to_model_api(image_bytes, user_id)

    if not api_result.get("success"):
        error_msg = api_result.get("reason", "Неизвестная ошибка")
        await msg.edit_text(f"❌ {error_msg}")
        return

    # !!! ВАЖНО: Распаковываем кортеж в ДВЕ переменные !!!
    # Мы передаем image_bytes вторым аргументом, чтобы draw_bounding_boxes сработал
    text, processed_image = format_response(api_result, image_bytes)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Верно", callback_data=f"fb:correct:{user_id}"),
        InlineKeyboardButton("❌ Ошибка", callback_data=f"fb:wrong:{user_id}")
    ]])

    user_sessions[user_id] = {"api_result": api_result, "feedback_given": False}

    # Удаляем сообщение "⏳ Нейросеть думает..."
    await msg.delete()

    # 3. Логика отправки результата
    if processed_image:
        # Если картинка есть — шлем ФОТО с подписью
        await update.message.reply_photo(
            photo=processed_image,
            caption=f"🍕 Результат: {text}",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        # Если картинки нет (например, ошибка в Pillow) — шлем только ТЕКСТ
        await update.message.reply_text(
            f"🍕 Результат: {text}",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, verdict, user_id_str = query.data.split(":")
    user_id = int(user_id_str)

    session = user_sessions.get(user_id)
    if not session or session["feedback_given"]:
        return

    session["feedback_given"] = True
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with aiohttp.ClientSession() as http:
        try:
            await http.post(FEEDBACK_URL, headers=headers, json={
                "user_id": user_id,
                "verdict": verdict,
                "original_result": session["api_result"]
            })
        except Exception as e:
            logger.warning(f"Ошибка фидбека: {e}")

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("🙏 Спасибо за отзыв!")


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^fb:"))
    logger.info("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
