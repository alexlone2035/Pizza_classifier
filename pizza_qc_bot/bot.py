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
    # 1. Твой ручной словарь соответствий (на основе фото)
    PIZZA_MAP = {
        "alfredo": "Альфредо",
        "bavarskaya": "Баварская",
        "bolshayabonanza": "Большая Бонанза",
        "chedderchizburger": "Чеддер Чизбургер",
        "cheddermeksikan": "Чеддер Мексикан",
        "chetyresyra": "Четыре Сыра",
        "chizburger": "Чизбургер",
        "gavayskaya": "Гавайская",
        "grushabbq": "Груша BBQ",
        "kaprichioza": "Капричоза",
        "klubnikaizefir": "Клубника и Зефир",
        "kosmicheskiyset23": "Космический сет 23",
        "krem_chizsgribami": "Крем-чиз с грибами",
        "lyubimayadedamoroza": "Любимая Деда Мороза",
        "lyubimayakarbonara": "Любимая Карбонара",
        "lyubimayapapinapitstsa": "Любимая Папина Пицца",
        "malenkayaitaliya": "Маленькая Италия",
        "margarita": "Маргарита",
        "meksikanskaya": "Мексиканская",
        "miksgrin": "Микс Грин",
        "myasnaya": "Мясная",
        "myasnoebarbekyu": "Мясное Барбекю",
        "novogodnyaya": "Новогодняя",
        "palochki": "Палочки",
        "papamiks": "Папа Микс",
        "pepperoni": "Пепперони",
        "pepperonigrin": "Пепперони Грин",
        "pitstsa8syrovnew": "Пицца 8 Сыров (Новая)",
        "postnaya": "Постная",
        "rozhdestvenskaya": "Рождественская",
        "sananasomibekonom": "С ананасом и беконом",
        "serdtsepepperoni_4syra": "Сердце Пепперони и 4 Сыра",
        "serdtsetsyplenokbarbekyu_pepperoni": "Сердце Цыпленок Барбекю и Пепперони",
        "sgrusheyibekonom": "С грушей и беконом",
        "sgrusheyigolubymsyrom": "С грушей и голубым сыром",
        "slivochnayaskrevetkami": "Сливочная с креветками",
        "superpapa": "Супер Папа",
        "syrnaya": "Сырная",
        "tomatnayaskrevetkami": "Томатная с креветками",
        "tsyplenokbarbekyu": "Цыпленок Барбекю",
        "tsyplenokflorentina": "Цыпленок Флорентина",
        "tsyplenokgrin": "Цыпленок Грин",
        "tsyplenokkordonblyu": "Цыпленок Кордон Блю",
        "tsyplenokkrench": "Цыпленок Кренч",
        "ulybka": "Улыбка",
        "vegetarianskaya": "Вегетарианская",
        "vetchinaibekon": "Ветчина и бекон",
        "vetchinaigriby": "Ветчина и грибы"
    }

    # 2. Получаем техническое имя из результата API
    raw_type = api_result.get('pizza_type', '').lower().strip()

    # 3. Ищем перевод в словаре
    # Если вдруг придет название, которого нет в списке — просто транслитерируем его
    if raw_type in PIZZA_MAP:
        return PIZZA_MAP[raw_type]

    # Fallback на случай, если слова нет в словаре (простой Capitalize)
    return raw_type.replace('_', ' ').capitalize()

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
    # if os.path.exists(image_path):
    #     os.remove(image_path)


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
