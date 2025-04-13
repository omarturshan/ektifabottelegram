import os
import asyncio
import requests
from bs4 import BeautifulSoup
from quart import Quart, request
from telegram import Update
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from pymongo import MongoClient

# إعدادات البيئة
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.environ.get("PORT", 5000))

# إعداد MongoDB
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["ektifa"]
chat_collection = db["chats"]

# إعداد OpenAI
openai = OpenAI(api_key=OPENAI_API_KEY)

# إنشاء تطبيق Quart وTelegram
web_app = Quart(__name__)
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

# رسالة ترحيبية
WELCOME_MESSAGE = "أهلاً بك في أكاديمية اكتفاء! كيف يمكنني مساعدتك اليوم؟"

# جلب معلومات من موقع اكتفاء
def fetch_ektifa_info():
    url = "https://ektifa.academy/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    about_section = soup.find("section", {"id": "about"}) or soup.find("section")
    text = about_section.get_text(separator="\n").strip() if about_section else "لم يتم العثور على معلومات من الموقع."
    return text

# هاندلر الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.effective_user.id

    if "اكتفاء" in user_message.lower() or "ektifa" in user_message.lower():
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

# هاندلر بدء المحادثة
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE)

# تسجيل الهاندلرز
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Webhook route
@web_app.route("/webhook", methods=["POST"])
async def webhook():
    data = await request.get_json()
    await telegram_app.update_queue.put(Update.de_json(data, telegram_app.bot))
    return "ok"




TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TOKEN)

WEBHOOK_URL = "https://ektifabottelegram.onrender.com/webhook"  # غيّرها لرابط مشروعك

async def set_webhook():
    await bot.set_webhook(url=WEBHOOK_URL)
    print("Webhook set!")

import asyncio
asyncio.run(set_webhook())












# تشغيل البوت وQuart معًا
async def main():
    await telegram_app.initialize()
    await telegram_app.start()
    print(f"Starting Quart server on port {PORT}")
    await web_app.run_task(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    asyncio.run(main())
