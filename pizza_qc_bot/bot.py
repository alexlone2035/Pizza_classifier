import os
import json
import io
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import anthropic
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import base64


# логи
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY")

# клиент anthropic
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)



PIZZA_ANALYSIS_PROMPT = """
Ты — эксперт по контролю качества пиццы на производстве.
Проанализируй фотографию пиццы и верни СТРОГО валидный JSON.

Структура ответа (только JSON, без markdown, без пояснений):
{
  "pizza_type": "Маргарита / Пепперони / Четыре сыра / Гавайская / Неизвестно",
  "overall_status": "OK" или "DEVIATION",
  "confidence": число от 0 до 100,
  "issues": [
    {
      "description": "Описание проблемы",
      "severity": "low" | "medium" | "high",
      "location": "верхний-левый" | "верхний-правый" | "нижний-левый" | "нижний-правый" | "центр" | "весь пирог",
      "bbox_hint": [x_percent, y_percent, width_percent, height_percent]
    }
  ],
  "positive_aspects": ["что выглядит хорошо"],
  "recommendation": "Краткая рекомендация для пекаря"
}

Проверяй:
- Равномерность распределения ингредиентов
- Цвет и степень запечённости корочки (должна быть золотистой)
- Наличие подгоревших участков
- Соответствие количества ингредиентов стандарту
- Целостность формы (не деформирована ли пицца)
- Видимые дефекты теста

bbox_hint — координаты в процентах от размера изображения [x, y, ширина, высота].
Если проблем нет, issues = [].
"""

# ХРАНИЛИЩЕ СОСТОЯНИЙ
# В продакшене замените на Redis или БД.
# Сейчас используем простой dict в памяти.
# Ключ: user_id, значение: данные последней проверки
user_sessions: dict = {}


async def analyze_pizza_with_claude(image_bytes: bytes) -> dict:
    """
    ТЕСТОВЫЙ РЕЖИМ — без обращения к API Anthropic.
    Возвращает фиктивные данные для проверки работы бота.
    """
    import random

    # Случайно выбираем — OK или с проблемами
    scenario = random.choice(["ok", "deviation"])

    if scenario == "ok":
        return {
            "pizza_type": "Маргарита",
            "overall_status": "OK",
            "confidence": 92,
            "issues": [],
            "positive_aspects": [
                "Равномерное распределение сыра",
                "Золотистая корочка",
                "Хорошая форма"
            ],
            "recommendation": "Пицца соответствует стандарту качества."
        }
    else:
        return {
            "pizza_type": "Пепперони",
            "overall_status": "DEVIATION",
            "confidence": 78,
            "issues": [
                {
                    "description": "Подгоревший край",
                    "severity": "high",
                    "location": "верхний-правый",
                    "bbox_hint": [60, 5, 35, 25]
                },
                {
                    "description": "Мало пепперони в центре",
                    "severity": "medium",
                    "location": "центр",
                    "bbox_hint": [30, 30, 40, 40]
                },
                {
                    "description": "Неравномерный сыр",
                    "severity": "low",
                    "location": "нижний-левый",
                    "bbox_hint": [5, 60, 30, 30]
                }
            ],
            "positive_aspects": [
                "Хорошая толщина теста"
            ],
            "recommendation": "Сократите время выпечки на 2 минуты, добавьте пепперони в центр."
        }


def draw_bounding_boxes(image_bytes: bytes, analysis: dict) -> bytes:
    """
    Рисует цветные bounding boxes на изображении.

    Цветовая схема:
    - Красный  = high severity (критично)
    - Оранжевый = medium severity (умеренно)
    - Жёлтый   = low severity (незначительно)
    - Зелёный  = рамка OK (если проблем нет)
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)

    W, H = img.size

    SEVERITY_COLORS = {
        "high": "#FF3333",
        "medium": "#FF8800",
        "low": "#FFD700",
    }

    issues = analysis.get("issues", [])

    if not issues:
        # Рисуем зелёную рамку — всё отлично!
        border = 6
        draw.rectangle(
            [border, border, W - border, H - border],
            outline="#00CC44",
            width=border
        )
        # Подпись
        draw.rectangle([0, H - 40, W, H], fill="#00CC44")
        draw.text(
            (W // 2, H - 20),
            "✅ КАЧЕСТВО В НОРМЕ",
            fill="white",
            anchor="mm"
        )
    else:
        for issue in issues:
            hint = issue.get("bbox_hint")
            if not hint or len(hint) != 4:
                # Если координаты не указаны — пропускаем
                continue

            # Переводим проценты в пиксели
            x = int(hint[0] / 100 * W)
            y = int(hint[1] / 100 * H)
            box_w = int(hint[2] / 100 * W)
            box_h = int(hint[3] / 100 * H)

            severity = issue.get("severity", "medium")
            color = SEVERITY_COLORS.get(severity, "#FF8800")

            # Рисуем прямоугольник
            draw.rectangle(
                [x, y, x + box_w, y + box_h],
                outline=color,
                width=3
            )

            # Подпись над рамкой
            label = issue.get("description", "Проблема")[:30]
            label_y = max(y - 22, 0)
            draw.rectangle(
                [x, label_y, x + len(label) * 7 + 8, label_y + 20],
                fill=color
            )
            draw.text(
                (x + 4, label_y + 2),
                label,
                fill="white"
            )

    # Сохраняем результат в байты
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=90)
    output.seek(0)
    return output.getvalue()


def format_result_message(analysis: dict) -> str:
    """
    Формирует читаемое сообщение из результатов анализа.
    """
    status = analysis.get("overall_status", "UNKNOWN")
    pizza = analysis.get("pizza_type", "Неизвестно")
    conf = analysis.get("confidence", 0)
    issues = analysis.get("issues", [])
    positives = analysis.get("positive_aspects", [])
    rec = analysis.get("recommendation", "")

    # Иконка статуса
    status_icon = "✅" if status == "OK" else "⚠️"
    verdict = "Всё в порядке" if status == "OK" else "Найдены отклонения"

    lines = [
        f"🍕 *Тип пиццы:* {pizza}",
        f"{status_icon} *Вердикт:* {verdict}",
        f"🎯 *Уверенность модели:* {conf}%",
        "",
    ]

    if issues:
        lines.append("*🔍 Обнаруженные проблемы:*")
        severity_icons = {"high": "🔴", "medium": "🟠", "low": "🟡"}
        for i, issue in enumerate(issues, 1):
            icon = severity_icons.get(issue.get("severity", "medium"), "🟠")
            lines.append(f"  {icon} {i}. {issue['description']}")
        lines.append("")

    if positives:
        lines.append("*👍 Хорошие стороны:*")
        for p in positives:
            lines.append(f"  ✓ {p}")
        lines.append("")

    if rec:
        lines.append(f"💡 *Рекомендация:* {rec}")

    return "\n".join(lines)



async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Привет! Я бот для проверки качества пиццы.*\n\n"
        "📸 *Как сделать хорошее фото для анализа:*\n"
        "  • Снимайте под углом 45° — так видны слои\n"
        "  • Пицца должна занимать бо́льшую часть кадра\n"
        "  • Хорошее освещение (без сильных теней)\n"
        "  • Не используйте фильтры\n\n"
        "Просто отправьте фото пиццы — и я всё проверю! 🍕"
    )
    await update.message.reply_text(text, parse_mode="Markdown")



async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Помощь*\n\n"
        "1. Отправьте фото пиццы\n"
        "2. Получите анализ с визуализацией\n"
        "3. Оцените точность модели кнопками\n\n"
        "Команды:\n"
        "/start — главное меню\n"
        "/help  — эта справка\n"
        "/stats — моя статистика проверок"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    logger.info(f"Фото получено от пользователя {user_id} ({user_name})")

    # Сообщаем, что начали обработку
    processing_msg = await update.message.reply_text(
        "⏳ Анализирую пиццу... Это займёт 5–10 секунд."
    )

    # ── Шаг 1: скачиваем фото ──────────────────
    # Telegram хранит несколько размеров — берём наибольший
    photo_file = await update.message.photo[-1].get_file()

    async with aiohttp.ClientSession() as session:
        async with session.get(photo_file.file_path) as resp:
            image_bytes = await resp.read()

    logger.info(f"Фото скачано: {len(image_bytes)} байт")

    # ── Шаг 2: анализируем через Claude ────────
    analysis = await analyze_pizza_with_claude(image_bytes)

    if "error" in analysis:
        await processing_msg.edit_text(
            "❌ Произошла ошибка при анализе. Попробуйте ещё раз.\n"
            f"Детали: {analysis.get('message', 'неизвестная ошибка')}"
        )
        return

    # ── Шаг 3: рисуем bounding boxes ───────────
    annotated_image = draw_bounding_boxes(image_bytes, analysis)

    # ── Шаг 4: формируем текст результата ──────
    result_text = format_result_message(analysis)

    # ── Шаг 5: кнопки обратной связи ───────────
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Модель права", callback_data=f"feedback:correct:{user_id}"),
            InlineKeyboardButton("❌ Модель ошиблась", callback_data=f"feedback:wrong:{user_id}"),
        ]
    ])

    # ── Шаг 6: сохраняем сессию ────────────────
    # Нужно для хранения контекста при получении обратной связи
    user_sessions[user_id] = {
        "analysis": analysis,
        "feedback_given": False,
        "correct_count": user_sessions.get(user_id, {}).get("correct_count", 0),
        "wrong_count": user_sessions.get(user_id, {}).get("wrong_count", 0),
    }

    # ── Шаг 7: отправляем результат ────────────
    await processing_msg.delete()

    await update.message.reply_photo(
        photo=io.BytesIO(annotated_image),
        caption=result_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # убираем "часики" на кнопке

    data = query.data  # формат: "feedback:correct:USER_ID"
    parts = data.split(":")

    if len(parts) != 3:
        return

    _, verdict, user_id_str = parts
    user_id = int(user_id_str)

    session = user_sessions.get(user_id)

    if not session:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Сессия устарела. Отправьте новое фото.")
        return

    if session.get("feedback_given"):
        await query.answer("Вы уже оценили этот результат!", show_alert=True)
        return

    # Фиксируем обратную связь
    session["feedback_given"] = True

    if verdict == "correct":
        session["correct_count"] = session.get("correct_count", 0) + 1
        response_text = (
            "✅ *Спасибо!* Рад, что анализ оказался точным.\n"
            "Ваш отзыв помогает улучшать модель. 🙏"
        )
    else:
        session["wrong_count"] = session.get("wrong_count", 0) + 1
        response_text = (
            "❌ *Понял, ошибся!* Спасибо за честный отзыв.\n"
            "Это поможет сделать модель точнее. 🙏"
        )

    # Убираем кнопки и отвечаем
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(response_text, parse_mode="Markdown")

    logger.info(f"Обратная связь от {user_id}: {verdict}")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, {})

    correct = session.get("correct_count", 0)
    wrong = session.get("wrong_count", 0)
    total = correct + wrong

    accuracy = f"{correct / total * 100:.0f}%" if total > 0 else "нет данных"

    text = (
        f"📊 *Ваша статистика*\n\n"
        f"Проверок оценено: {total}\n"
        f"✅ Модель была права: {correct}\n"
        f"❌ Модель ошиблась: {wrong}\n"
        f"🎯 Точность по вашим данным: {accuracy}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")






def main():

    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGAM_BOT_TOKEN не задан в .env")
    if not ANTHROPIC_KEY:
        raise ValueError("ANTHROPIC_API_KEY не задан в .env")

    logger.info("Запуск Pizza QC Bot...")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^feedback:"))

    logger.info("Бот запущен. Ожидаю фотографии пицц...")

    app.run_polling(allowed_updates=Update.ALL_TYPES)



if __name__ == "__main__":
    main()

