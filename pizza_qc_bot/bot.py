import os
import logging
import aiohttp
import io

from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
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
        return (255, 0, 0)
    elif conf < 0.8:
        return (255, 200, 0)
    else:
        return (0, 200, 0)




def draw_boxes(image_bytes: bytes, pizzas: list) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.load_default()
    except:
        font = None

    for pizza in pizzas:
        x1, y1, x2, y2 = pizza["box"]
        conf = float(pizza["confidence"])
        label = f"{pizza['pizza_type']} ({conf:.2f})"

        color = get_color(conf)

        # рамка
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

        # размер текста
        text_bbox = draw.textbbox((0, 0), label, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]

        # фон под текст
        text_y = max(y1 - text_h - 4, 0)
        draw.rectangle(
            [x1, text_y, x1 + text_w + 6, text_y + text_h + 4],
            fill=color
        )

        # текст
        draw.text((x1 + 3, text_y + 2), label, fill="white", font=font)

    output = io.BytesIO()
    img.save(output, format="JPEG", quality=90)
    return output.getvalue()




def format_response(data):
    if not data.get("success"):
        return f"❌ {data.get('report')}"

    text = f"📋 {data.get('report')}\n"

    for i, p in enumerate(data.get("pizzas", []), 1):
        text += f"\n{i}. {p['pizza_type']} (Уверенность модели - {p['confidence']})"

    return text


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Получена команда /start")

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👋 Привет! Пришли фото пиццы, и я определю её вид."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    msg = await update.message.reply_text("⏳ Нейросеть думает...")

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
        InlineKeyboardButton("✅ Верно", callback_data=f"fb:correct:{prediction_id}"),
        InlineKeyboardButton("❌ Не верно", callback_data=f"fb:wrong:{prediction_id}")
    ]])

    await msg.delete()

    # 🎨 рисуем bbox через Pillow
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
        async with session.post(
            FEEDBACK_URL,
            json={
                "prediction_id": int(prediction_id),
                "verdict": verdict
            },
            headers=headers
        ) as resp:
            pass

    await query.edit_message_reply_markup(None)
    await query.message.reply_text("Спасибо за отзыв!")




def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(feedback))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()