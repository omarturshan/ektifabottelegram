import os
import asyncio
import requests
from bs4 import BeautifulSoup
from quart import Quart, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from pymongo import MongoClient

# -------------- إعداد المتغيرات --------------
TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")
MONGODB_URI     = os.getenv("MONGODB_URI")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
PORT            = int(os.environ.get("PORT", 5000))

# رابط موقع الأكاديمية الذي يُسحب منه المحتوى
EKTIFA_URL      = "https://ektifa-academy.com/"

# -------------- إعداد MongoDB --------------
mongo_client    = MongoClient(MONGODB_URI)
db              = mongo_client["ektifa"]
chat_collection = db["chats"]

# -------------- إعداد OpenAI --------------
openai = OpenAI(api_key=OPENAI_API_KEY)

# -------------- إنشاء تطبيقات Quart و Telegram --------------
web_app      = Quart(__name__)
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

WELCOME_MESSAGE = "أهلاً بك في أكاديمية اكتفاء! كيف يمكنني مساعدتك اليوم؟"

# -------------- دالة جلب المعلومات من الموقع --------------
def fetch_ektifa_info():
    """يجلب بيانات OG من صفحة الأكاديمية ليعرضها في البوت."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(EKTIFA_URL, headers=headers, timeout=10)
        r.raise_for_status()
    except Exception as e:
        return None, f"⚠️ تعذّر جلب بيانات الأكاديمية ({e})"

    soup = BeautifulSoup(r.text, "html.parser")

    def meta_prop(prop_name):
        tag = soup.find("meta", property=prop_name)
        return tag["content"].strip() if tag and tag.has_attr("content") else None

    title       = meta_prop("og:title")       or "أكاديمية اكتفاء"
    description = meta_prop("og:description") or "أكاديمية اكتفاء للتدريب والاستشارات."
    image       = meta_prop("og:image")       or EKTIFA_URL + "logo.png"
    page_url    = meta_prop("og:url")         or EKTIFA_URL

    info = (
        f"*{title}*\n\n"
        f"{description}\n\n"
        f"🌐 [الموقع الرسمي]({page_url})"
    )
    return image, info

# -------------- معالج الرسائل --------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text or ""
    uid = update.effective_user.id

    if "اكتفاء" in txt.lower() or "ektifa" in txt.lower():
        image, info = fetch_ektifa_info()

        # أرسل الصورة أولًا (إذا وجدنا رابط)
        if image:
            await update.message.reply_photo(photo=image)

        # ثم أرسل النص مقسّم إلى أجزاء ≤1000 حرف
        MAX = 1000
        for i in range(0, len(info), MAX):
            chunk = info[i:i+MAX]
            await update.message.reply_text(chunk, parse_mode="Markdown")
        reply = info
    else:
        # تفاعل مع OpenAI للردود العامة
        comp = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "أجب كأنك موظف في أكاديمية اكتفاء، وبأسلوب ودود وإيجاز."},
                {"role": "user",   "content": txt},
            ]
        )
        reply = comp.choices[0].message.content
        await update.message.reply_text(reply)

    # حفظ المحادثة في MongoDB
    chat_collection.insert_one({
        "user_id": uid,
        "message": txt,
        "reply":   reply
    })

# -------------- معالج /start --------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE)

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# -------------- نقطة ويب هوك --------------
@web_app.route("/webhook", methods=["POST"])
async def webhook():
    data   = await request.get_json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return "OK"

# -------------- تشغيل البوت والخادم معًا --------------
async def main():
    await telegram_app.initialize()
    await telegram_app.start()
    await web_app.run_task(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    asyncio.run(main())
