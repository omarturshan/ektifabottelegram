import os
import httpx
from quart import Quart, request
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from pymongo import MongoClient

# --- إعداد البيئة ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ZENROWS_API_KEY = os.getenv("ZENROWS_API_KEY")

# --- MongoDB ---
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["ektifa"]
chat_collection = db["chats"]

# --- OpenAI ---
openai = OpenAI(api_key=OPENAI_API_KEY)

# --- Telegram ---
app = Application.builder().token(TELEGRAM_TOKEN).build()

# --- Quart Web Server ---
web_app = Quart(__name__)

WELCOME_MESSAGE = "أهلاً بك في أكاديمية اكتفاء! كيف يمكنني مساعدتك اليوم؟"

async def fetch_ektifa_content():
    url = "https://ektifa-academy.com/"
    api_url = f"https://api.zenrows.com/v1/?apikey={ZENROWS_API_KEY}&url={url}&js_render=true"

    async with httpx.AsyncClient() as client:
        response = await client.get(api_url)
        if response.status_code == 200:
            return response.text
        else:
            return None

async def extract_about_us_from_html(html):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    section = soup.find("section", {"id": "about"}) or soup.find("section", string=lambda x: "من نحن" in x if x else False)
    
    if section:
        text = section.get_text(separator="\n", strip=True)
        return text[:900]  # Telegram limit safe
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.effective_user.id

    # تحقق إن كان المستخدم يسأل عن اكتفاء
    if "اكتفاء" in user_message.lower() or "ektifa" in user_message.lower():
        html = await fetch_ektifa_content()
        if html:
            about_text = await extract_about_us_from_html(html)
            if about_text:
                # إرسال الشعار أولاً
                await update.message.reply_photo("https://ektifa-academy.com/assets/images/logo.png")
                # إرسال النص
                await update.message.reply_text(about_text)
            else:
                await update.message.reply_text("عذرًا، لم أتمكن من استخراج المعلومات من الموقع حالياً.")
        else:
            await update.message.reply_text("عذرًا، لم أتمكن من الوصول للموقع.")
        return

    # الرد الطبيعي من OpenAI
    completion = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "أجب كأنك موظف في أكاديمية اكتفاء، بإيجاز ووضوح وبأسلوب ودود."},
            {"role": "user", "content": user_message},
        ]
    )
    reply = completion.choices[0].message.content

    await update.message.reply_text(reply)

    # حفظ المحادثة
    chat_collection.insert_one({
        "user_id": user_id,
        "message": user_message,
        "reply": reply
    })

# أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE)

# تسجيل الأوامر
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Webhook route
@web_app.route("/webhook", methods=["POST"])
async def webhook():
    data = await request.get_json()
    await app.update_queue.put(Update.de_json(data, app.bot))
    return "ok"

# تشغيل البوت
if __name__ == "__main__":
    import asyncio
    from bs4 import BeautifulSoup  # مهم لاستخدامه مع ZenRows
    asyncio.run(app.initialize())
    web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
