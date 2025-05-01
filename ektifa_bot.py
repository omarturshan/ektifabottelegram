import os
import json
import requests
import asyncio
from quart import Quart, request
from telegram import Bot
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from pymongo import MongoClient

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ZENROWS_API_KEY = os.getenv("ZENROWS_API_KEY")

mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["ektifa"]
chat_collection = db["chats"]

openai = OpenAI(api_key=OPENAI_API_KEY)
app = Application.builder().token(TELEGRAM_TOKEN).build()
web_app = Quart(__name__)

WELCOME_MESSAGE = "أهلاً بك في أكاديمية اكتفاء! كيف يمكنني مساعدتك اليوم؟"

# دالة لجلب معلومات من موقع اكتفاء باستخدام ZenRows
def fetch_ektifa_info():
    url = "https://ektifa-academy.com/about-us"
    zen_api = f"https://api.zenrows.com/v1/?apikey={ZENROWS_API_KEY}&url={url}&js_render=true"
    response = requests.get(zen_api)
    if response.status_code == 200:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        content = soup.get_text(separator="\n").strip()
        return content[:4000]  # Telegram limit
    else:
        return "لم أتمكن من جلب المعلومات من الموقع حالياً."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.effective_user.id

    if any(keyword in user_message.lower() for keyword in ["اكتفاء", "من هي اكتفاء", "ما هي اكاديمية اكتفاء", "ektifa"]):
        reply = fetch_ektifa_info()
    else:
        completion = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "أجب كأنك موظف في أكاديمية اكتفاء، بإيجاز ووضوح وبأسلوب ودود."},
                {"role": "user", "content": user_message},
            ]
        )
        reply = completion.choices[0].message.content

    await update.message.reply_text(reply)

    chat_collection.insert_one({
        "user_id": user_id,
        "message": user_message,
        "reply": reply
    })

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE)

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@web_app.route("/webhook", methods=["POST"])
async def webhook():
    data = await request.get_data()
    update = Update.de_json(json.loads(data.decode("utf-8")), bot=app.bot)
    await app.update_queue.put(update)
    return "OK"



async def set_webhook():
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    bot = Bot(token=TOKEN)
    url = "https://ektifabottelegram.onrender.com/webhook"  # غير هذا للرابط الصحيح
    success = await bot.set_webhook(url)
    print("Webhook set:", success)

if __name__ == "__main__":
    asyncio.run(set_webhook())





if __name__ == "__main__":
    import asyncio
    asyncio.run(app.initialize())
    web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
