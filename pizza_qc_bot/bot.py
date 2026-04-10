import os
import logging
import aiohttp
import io
import cv2
import numpy as np

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")

PREDICT_URL = f"{API_BASE_URL}/predict"
FEEDBACK_URL = f"{API_BASE_URL}/feedback"

async def send_to_api(image_bytes, user_id):
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with aiohttp.ClientSession() as session:
        form = aiohttp.FormData()
        form.add_field("file", image_bytes, filename="pizza.jpg", content_type="image/jpeg")
        form.add_field("chat_id", str(user_id))

        async with session.post(PREDICT_URL, data=form, headers=headers) as resp:
            return await resp.json()


def get_color(conf):
    if conf < 0.5:
        return (0, 0, 255)
    elif conf < 0.8:
        return (0, 255, 255)
    else:
        return (0, 255, 0)


def draw_boxes(image_bytes: bytes, pizzas: list) -> bytes:
    np_arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    for pizza in pizzas:
        x1, y1, x2, y2 = pizza["box"]
        conf = float(pizza["confidence"])
        label = f"{pizza['pizza_type']} ({conf:.2f})"

        color = get_color(conf)

        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            img,
            label,
            (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2
        )

    _, buffer = cv2.imencode(".jpg", img)
    return buffer.tobytes()


def format_response(data):
    if not data.get("success"):
        return f"❌ {data.get('report')}"

    text = f"📋 {data.get('report')}\n"

    for i, p in enumerate(data.get("pizzas", []), 1):
        text += f"\n{i}. {p['pizza_type']} ({p['confidence']})"

    return text


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    msg = await update.message.reply_text("⏳ Обрабатываю...")

    photo = await update.message.photo[-1].get_file()

    async with aiohttp.ClientSession() as s:
        async with s.get(photo.file_path) as r:
            image_bytes = await r.read()

    result = await send_to_api(image_bytes, user_id)

    if result.get("error"):
        await msg.edit_text("❌ Ошибка API")
        return

    text = format_response(result)
    prediction_id = result.get("prediction_id")

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅", callback_data=f"fb:correct:{prediction_id}"),
        InlineKeyboardButton("❌", callback_data=f"fb:wrong:{prediction_id}")
    ]])

    await msg.delete()

    if result.get("pizzas"):
        img = draw_boxes(image_bytes, result["pizzas"])
        bio = io.BytesIO(img)
        bio.name = "result.jpg"

        await update.message.reply_photo(
            photo=bio,
            caption=text,
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(text, reply_markup=keyboard)


async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, verdict, prediction_id = query.data.split(":")

    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with aiohttp.ClientSession() as session:
        await session.post(
            FEEDBACK_URL,
            json={
                "prediction_id": int(prediction_id),
                "verdict": verdict
            },
            headers=headers
        )

    await query.edit_message_reply_markup(None)
    await query.message.reply_text("Спасибо за отзыв!")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(feedback))

    app.run_polling()


if __name__ == "__main__":
    main()