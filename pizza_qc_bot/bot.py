import os
import logging
import aiohttp
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


def format_response(api_result: dict) -> str:
    PIZZA_MAP = {
        "alfredo": "Альфредо", "bavarskaya": "Баварская", "bolshayabonanza": "Большая Бонанза",
        "chedderchizburger": "Чеддер Чизбургер", "cheddermeksikan": "Чеддер Мексикан",
        "chetyresyra": "Четыре Сыра", "chizburger": "Чизбургер", "gavayskaya": "Гавайская",
        "grushabbq": "Груша BBQ", "kaprichioza": "Капричоза", "klubnikaizefir": "Клубника и Зефир",
        "kosmicheskiyset23": "Космический сет 23", "krem_chizsgribami": "Крем-чиз с грибами",
        "lyubimayadedamoroza": "Любимая Деда Мороза", "lyubimayakarbonara": "Любимая Карбонара",
        "lyubimayapapinapitstsa": "Любимая Папина Пицца", "malenkayaitaliya": "Маленькая Италия",
        "margarita": "Маргарита", "meksikanskaya": "Мексиканская", "miksgrin": "Микс Грин",
        "myasnaya": "Мясная", "myasnoebarbekyu": "Мясное Барбекю", "novogodnyaya": "Новогодняя",
        "palochki": "Палочки", "papamiks": "Папа Микс", "pepperoni": "Пепперони",
        "pepperonigrin": "Пепперони Грин", "pitstsa8syrovnew": "Пицца 8 Сыров (Новая)",
        "postnaya": "Постная", "rozhdestvenskaya": "Рождественская", "sananasomibekonom": "С ананасом и беконом",
        "serdtsepepperoni_4syra": "Сердце Пепперони и 4 Сыра",
        "serdtsetsyplenokbarbekyu_pepperoni": "Сердце Цыпленок Барбекю и Пепперони",
        "sgrusheyibekonom": "С грушей и беконом", "sgrusheyigolubymsyrom": "С грушей и голубым сыром",
        "slivochnayaskrevetkami": "Сливочная с креветками", "superpapa": "Супер Papa",
        "syrnaya": "Сырная", "tomatnayaskrevetkami": "Томатная с креветками",
        "tsyplenokbarbekyu": "Цыпленок Барбекю", "tsyplenokflorentina": "Цыпленок Флорентина",
        "tsyplenokgrin": "Цыпленок Грин", "tsyplenokkordonblyu": "Цыпленок Кордон Блю",
        "tsyplenokkrench": "Цыпленок Кренч", "ulybka": "Улыбка", "vegetarianskaya": "Вегетарианская",
        "vetchinaibekon": "Ветчина и бекон", "vetchinaigriby": "Ветчина и грибы"
    }

    INGREDIENTS_MAP = {
        'pepperoni': 'Пепперони', 'chicken': 'Курица', 'mushroom': 'Грибы',
        'tomato': 'Томаты', 'pineapple': 'Ананас', 'bacon': 'Бекон',
        'ham': 'Ветчина', 'shrimp': 'Креветки', 'cheese': 'Сыр',
        'olive': 'Оливки', 'pepper': 'Перец', 'jalapeno': 'Халапеньо', 'onion': 'Лук'
    }

    raw_type = api_result.get('pizza_type', '').lower().strip()
    pizza_name = PIZZA_MAP.get(raw_type, raw_type.replace('_', ' ').capitalize())

    status = api_result.get('status', '')
    status_icon = "✅" if status == "OK" else "❌"

    raw_reason = api_result.get('reason', '')
    if isinstance(raw_reason, list):
        translated_list = [INGREDIENTS_MAP.get(r.lower(), r) for r in raw_reason]
        reason_text = ", ".join(translated_list)
    else:
        reason_text = INGREDIENTS_MAP.get(str(raw_reason).lower(), raw_reason)

    if status != "OK" and reason_text:
        reason_full = f"Уважаемый клиент, Ваша проблема заключается в следующих ингредиентах: {reason_text}"
    else:
        reason_full = f"Причина: {reason_text}" if reason_text else ""

    return f"*{pizza_name}*\nСтатус: {status_icon} {status}\n{reason_full}"



async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Пришли фото пиццы, и я определю её вид.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = await update.message.reply_text("⏳ Нейросеть думает...")

    photo_file = await update.message.photo[-1].get_file()
    async with aiohttp.ClientSession() as session:
        async with session.get(photo_file.file_path) as resp:
            image_bytes = await resp.read()

    api_result = await send_to_model_api(image_bytes, user_id)

    if not api_result.get("success"):
        error_msg = api_result.get("reason", "Неизвестная ошибка")
        await msg.edit_text(f"❌ {error_msg}")
        return

    text = format_response(api_result)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Верно", callback_data=f"fb:correct:{user_id}"),
        InlineKeyboardButton("❌ Ошибка", callback_data=f"fb:wrong:{user_id}")
    ]])

    user_sessions[user_id] = {"api_result": api_result, "feedback_given": False}

    await msg.delete()
    await update.message.reply_text(f"🍕 Результат:\n{text}", reply_markup=keyboard)


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