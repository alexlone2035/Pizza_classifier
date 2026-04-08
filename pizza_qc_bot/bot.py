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

if not TELEGRAM_TOKEN or not API_BASE_URL or not API_KEY:
    raise ValueError("Проверьте переменные окружения (Token, API_URL, Key)")

PREDICT_URL  = f"{API_BASE_URL}/predict"
FEEDBACK_URL = f"{API_BASE_URL}/feedback"

user_sessions: dict = {}

# ─────────────────────────────────────────────
# ОТПРАВКА В API (ФОТО + CHAT_ID)
# ─────────────────────────────────────────────
async def send_to_model_api(image_bytes: bytes, user_id: int) -> dict:
    logger.info(f"Отправка в API: {PREDICT_URL} для пользователя {user_id}")

    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with aiohttp.ClientSession() as session:
        form = aiohttp.FormData()
        
        # Отправляем файл
        form.add_field(
            "file",
            image_bytes,
            filename="pizza.jpg",
            content_type="image/jpeg"
        )
        
        # Отправляем chat_id (сокомандник получит его в request.form)
        form.add_field("chat_id", str(user_id))

        try:
            async with session.post(
                PREDICT_URL,
                data=form,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result
                else:
                    text = await resp.text()
                    logger.error(f"Ошибка API {resp.status}: {text}")
                    return {"error": True, "message": f"Ошибка сервера: {resp.status}"}
        except Exception as e:
            return {"error": True, "message": f"Ошибка соединения: {str(e)}"}


# ─────────────────────────────────────────────
# ФОРМАТ ОТВЕТА (РУЧНОЙ СЛОВАРЬ)
# ─────────────────────────────────────────────
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
        "slivochnayaskrevetkami": "Сливочная с креветками", "superpapa": "Супер Папа",
        "syrnaya": "Сырная", "tomatnayaskrevetkami": "Томатная с креветками",
        "tsyplenokbarbekyu": "Цыпленок Барбекю", "tsyplenokflorentina": "Цыпленок Флорентина",
        "tsyplenokgrin": "Цыпленок Грин", "tsyplenokkordonblyu": "Цыпленок Кордон Блю",
        "tsyplenokkrench": "Цыпленок Кренч", "ulybka": "Улыбка", "vegetarianskaya": "Вегетарианская",
        "vetchinaibekon": "Ветчина и бекон", "vetchinaigriby": "Ветчина и грибы"
    }
    raw_type = api_result.get('pizza_type', '').lower().strip()
    return PIZZA_MAP.get(raw_type, raw_type.replace('_', ' ').capitalize())

# ─────────────────────────────────────────────
# ОБРАБОТЧИКИ ТЕЛЕГРАМ
# ─────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Пришли фото пиццы, и я определю её вид.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = await update.message.reply_text("⏳ Нейросеть думает...")

    # Скачиваем фото в память
    photo_file = await update.message.photo[-1].get_file()
    async with aiohttp.ClientSession() as session:
        async with session.get(photo_file.file_path) as resp:
            image_bytes = await resp.read()

    # Отправляем сокоманднику (фото + ID)
    api_result = await send_to_model_api(image_bytes, user_id)

    if api_result.get("error"):
        await msg.edit_text(f"❌ {api_result['message']}")
        return

    text = format_response(api_result)
    
    # Кнопки фидбека
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Верно", callback_data=f"fb:correct:{user_id}"),
        InlineKeyboardButton("❌ Ошибка", callback_data=f"fb:wrong:{user_id}")
    ]])

    user_sessions[user_id] = {"api_result": api_result, "feedback_given": False}

    await msg.delete()
    await update.message.reply_text(f"Результат: *{text}*", parse_mode="Markdown", reply_markup=keyboard)

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
