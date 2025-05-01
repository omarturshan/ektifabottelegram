import os
import json
import requests
import asyncio
from quart import Quart, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI
from pymongo import MongoClient
from bs4 import BeautifulSoup

# إعداد المتغيرات
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ZENROWS_API_KEY = os.getenv("ZENROWS_API_KEY")

# اتصال MongoDB
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["ektifa"]
chat_collection = db["chats"]

# إعداد OpenAI
openai = OpenAI(api_key=OPENAI_API_KEY)

# إعداد التطبيقات
app = Application.builder().token(TELEGRAM_TOKEN).build()
web_app = Quart(__name__)

WELCOME_MESSAGE = "أهلاً بك في أكاديمية اكتفاء! كيف يمكنني مساعدتك اليوم؟"

# دالة لجلب معلومات من ZenRows
def fetch_ektifa_info():
    url = "https://ektifa-academy.com/about-us"
    zen_api = f"https://api.zenrows.com/v1/?apikey={ZENROWS_API_KEY}&url={url}&js_render=true"
    response = requests.get(zen_api)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        content = soup.get_text(separator="\n").strip()
        return content[:4000]
    return "لم أتمكن من جلب المعلومات من الموقع حالياً."

# الرد على الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.effective_user.id
    print("📩 Received message:", update.message.text)


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

# أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE)

# ربط المعالجات
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Route للـ Webhook
@web_app.route("/webhook", methods=["POST"])
async def webhook():
    data = await request.get_data()
    update = Update.de_json(json.loads(data.decode("utf-8")), app.bot)
    await app.update_queue.put(update)
    return "OK"

# التشغيل الكامل
async def main():
    await app.initialize()

    # تعيين Webhook
    bot = Bot(token=TELEGRAM_TOKEN)
    webhook_url = "https://ektifabottelegram.onrender.com/webhook"
    await bot.delete_webhook()
    success = await bot.set_webhook(url=webhook_url)
    print("✅ Webhook تم تفعيله:", success)

    # تشغيل السيرفر
    await web_app.run_task(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    asyncio.run(main())
