import os
from quart import Quart, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from pymongo import MongoClient

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# MongoDB setup
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["ektifa"]
chat_collection = db["chats"]

# OpenAI setup
openai = OpenAI(api_key=OPENAI_API_KEY)

# Telegram app setup
app = Application.builder().token(TELEGRAM_TOKEN).build()

# Quart app for webhook
web_app = Quart(__name__)

# رسالة ترحيبية
WELCOME_MESSAGE = "أهلاً بك في أكاديمية اكتفاء! كيف يمكنني مساعدتك اليوم؟"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.effective_user.id

    # إرسال السؤال إلى OpenAI
    completion = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "أجب كأنك موظف في أكاديمية اكتفاء، بإيجاز ووضوح وبأسلوب ودود."},
            {"role": "user", "content": user_message},
        ]
    )

    reply = completion.choices[0].message.content

    # إرسال الرد للمستخدم
    await update.message.reply_text(reply)

    # حفظ المحادثة في MongoDB
    chat_collection.insert_one({
        "user_id": user_id,
        "message": user_message,
        "reply": reply
    })

# نقطة البداية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE)

# تسجيل الهاندلرز
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Webhook endpoint
@web_app.route("/webhook", methods=["POST"])
async def webhook():
    json_data = await request.get_json()
    update = Update.de_json(json_data, app.bot)
    await app.process_update(update)
    return "ok"


# تشغيل البوت
if __name__ == "__main__":
    import asyncio
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    async def run():
        await app.initialize()
        config = Config()
        config.bind = [f"0.0.0.0:{os.environ.get('PORT', '5000')}"]
        await serve(web_app, config)

    asyncio.run(run())
