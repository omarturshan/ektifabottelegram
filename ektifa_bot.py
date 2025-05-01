import os
import asyncio
from quart import Quart, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI
from pymongo import MongoClient

# إعداد التوكنات
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# إعداد MongoDB
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["ektifa"]
chat_collection = db["chats"]

# إعداد OpenAI
openai = OpenAI(api_key=OPENAI_API_KEY)

# إعداد تطبيق تيليجرام
app = Application.builder().token(TELEGRAM_TOKEN).build()

# إعداد تطبيق الويب بـ Quart
web_app = Quart(__name__)

# رسالة ترحيب
WELCOME_MESSAGE = "أهلاً بك في أكاديمية اكتفاء! كيف يمكنني مساعدتك اليوم؟"

# بدء المحادثة
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE)

# معالجة الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.effective_user.id

    # طلب من OpenAI
    completion = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "أجب كأنك موظف في أكاديمية اكتفاء، بإيجاز ووضوح وبأسلوب ودود."},
            {"role": "user", "content": user_message}
        ]
    )

    reply = completion.choices[0].message.content
    await update.message.reply_text(reply)

    # حفظ المحادثة في MongoDB
    chat_collection.insert_one({
        "user_id": user_id,
        "message": user_message,
        "reply": reply
    })

# تسجيل الأوامر
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# نقطة الاتصال بالويب هوك
@web_app.route("/webhook", methods=["POST"])
async def webhook():
    data = await request.get_data()
    update = Update.de_json(data.decode("utf-8"), app.bot)
    await app.update_queue.put(update)
    return "OK"

# تشغيل التطبيق باستخدام Hypercorn
if __name__ == "__main__":
    async def main():
        await app.initialize()
        await app.start()
        import hypercorn.asyncio
        from hypercorn.config import Config

        config = Config()
        config.bind = [f"0.0.0.0:{os.environ.get('PORT', '5000')}"]
        await hypercorn.asyncio.serve(web_app, config)

    asyncio.run(main())
