import os
import logging
import aiohttp
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)


# ─────────────────────────────────────────────
# КОНФИГ
# ─────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE_URL   = os.getenv("API_BASE_URL")     # http://api:8000
API_KEY        = os.getenv("API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не задан")

if not API_BASE_URL:
    raise ValueError("API_BASE_URL не задан")

if not API_KEY:
    raise ValueError("API_KEY не задан")

PREDICT_URL  = f"{API_BASE_URL}/predict"
FEEDBACK_URL = f"{API_BASE_URL}/feedback"

# ─────────────────────────────────────────────
# СЕССИИ
# ─────────────────────────────────────────────
user_sessions: dict = {}


# ─────────────────────────────────────────────
# ОТПРАВКА В API
# ─────────────────────────────────────────────
async def send_to_model_api(image_bytes: bytes, user_id: int) -> dict:
    logger.info(f"Отправка в API: {PREDICT_URL}")

    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    async with aiohttp.ClientSession() as session:
        form = aiohttp.FormData()

        # ❗ ВАЖНО: должно быть "file"
        form.add_field(
            "file",
            image_bytes,
            filename="pizza.jpg",
            content_type="image/jpeg"
        )

        try:
            async with session.post(
                PREDICT_URL,
                data=form,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:

                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"Ответ API: {result}")
                    return result
                else:
                    text = await resp.text()
                    logger.error(f"Ошибка API {resp.status}: {text}")
                    return {"error": True, "message": f"Ошибка {resp.status}"}

        except aiohttp.ClientConnectorError:
            return {"error": True, "message": "API недоступен"}

        except Exception as e:
            return {"error": True, "message": str(e)}


# ─────────────────────────────────────────────
# ФОРМАТ ОТВЕТА
# ─────────────────────────────────────────────
def format_response(api_result: dict) -> str:
    # Словари для перевода терминов
    pizza_translations = {
        "Margherita": "Маргарита",
        "Pepperoni": "Пепперони",
        "Meat": "Мясная",
        "Cheese": "Сырная",
        "Hawaiian": "Гавайская",
        "Veggie": "Овощная"
    }

    status_translations = {
        "OK": "✅ Соответствует стандарту",
        "NOT_OK": "❌ Брак / Несоответствие",
        "ERROR": "⚠️ Ошибка обработки"
    }

    # Получаем значения из API (в английском варианте)
    raw_type = api_result.get('pizza_type', '—')
    raw_status = api_result.get('status', '—')
    confidence = api_result.get('confidence', '0')
    reason = api_result.get('reason', '')

    # Переводим, если значение есть в словаре, иначе оставляем как есть
    translated_type = pizza_translations.get(raw_type, raw_type)
    translated_status = status_translations.get(raw_status, raw_status)

    # Если "reason" тоже приходит на английском, можно добавить простую замену
    # Например: "Not enough salami" -> "Недостаточно колбасы"
    reason_ru = reason.replace("Not enough salami", "Недостаточно колбасы") \
                      .replace("Wrong ingredients", "Неверные ингредиенты") \
                      .replace("With pizza everything is fine", "С пиццей всё в порядке")

    return (
        f"📋 *Результат проверки*\n\n"
        f"🍕 *Тип:* `{translated_type}`\n"
        f"📊 *Уверенность:* `{confidence}%`\n"
        f"🛡️ *Статус:* {translated_status}\n"
        f"📝 *Причина:* {reason_ru}"
    )

# ─────────────────────────────────────────────
# КОМАНДЫ
# ─────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Отправь фото пиццы")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Просто отправь фото")


# ─────────────────────────────────────────────
# ОБРАБОТКА ФОТО
# ─────────────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    msg = await update.message.reply_text("⏳ Обрабатываю...")

    photo = await update.message.photo[-1].get_file()

    async with aiohttp.ClientSession() as session:
        async with session.get(photo.file_path) as resp:
            image_bytes = await resp.read()


    api_result = await send_to_model_api(image_bytes, user_id)

    if api_result.get("error"):
        await msg.edit_text(f"❌ {api_result['message']}")
        return

    text = format_response(api_result)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅", callback_data=f"fb:correct:{user_id}"),
        InlineKeyboardButton("❌", callback_data=f"fb:wrong:{user_id}")
    ]])

    user_sessions[user_id] = {
        "api_result": api_result,
        "feedback_given": False
    }

    await msg.delete()
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

    # Рекомендуется удалить временный файл после обработки
    if os.path.exists(image_path):
        os.remove(image_path)


# ─────────────────────────────────────────────
# FEEDBACK
# ─────────────────────────────────────────────
async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, verdict, user_id_str = query.data.split(":")
    user_id = int(user_id_str)

    session = user_sessions.get(user_id)
    if not session:
        return

    if session["feedback_given"]:
        await query.answer("Уже оценено", show_alert=True)
        return

    session["feedback_given"] = True

    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    async with aiohttp.ClientSession() as http:
        try:
            await http.post(
                FEEDBACK_URL,
                json={
                    "user_id": user_id,
                    "verdict": verdict,
                    "original_result": session["api_result"]
                },
                headers=headers
            )
        except Exception as e:
            logger.warning(f"feedback error: {e}")

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("✅ Спасибо!")


# ─────────────────────────────────────────────
# ЗАПУСК
# ─────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^fb:"))

    app.run_polling()


if __name__ == "__main__":
    main()
