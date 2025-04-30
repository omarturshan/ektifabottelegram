import os
import asyncio
import requests
from bs4 import BeautifulSoup
from quart import Quart, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from pymongo import MongoClient

# --- إعداد المتغيرات من البيئة ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MONGODB_URI    = os.getenv("MONGODB_URI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT           = int(os.environ.get("PORT", 5000))

# --- إعداد MongoDB ---
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["ektifa"]
chat_collection = db["chats"]

# --- إعداد OpenAI ---
openai = OpenAI(api_key=OPENAI_API_KEY)

# --- إنشاء تطبيقات Quart و Telegram ---
web_app      = Quart(__name__)
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

# رسالة ترحيبية
WELCOME_MESSAGE = "أهلاً بك في أكاديمية اكتفاء! كيف يمكنني مساعدتك اليوم؟"

# دالة لجلب المعلومات من الموقع مع HEADERS
def fetch_ektifa_info():
    url = "https://ektifa.academy/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return f"⚠️ حدث خطأ أثناء جلب معلومات الأكاديمية: {e}"

    soup = BeautifulSoup(resp.text, "html.parser")

    # القسم "من نحن" غالبًا داخل <section> برقم معين أو class
    about = soup.find("section", {"id": "about"}) or soup.find("div", class_="about-us") or soup
    about_text = about.get_text(separator="\n").strip()

    # الدورات (مثال: جميع عناصر <h3> تحت class="courses")
    courses = soup.select(".courses h3")
    courses_text = "\n".join(f"- {c.get_text(strip=True)}" for c in courses) or "غير متوفرة"

    # وسائل التواصل (مثال: روابط <a> داخل footer أو class="social")
    social = soup.select(".social a")
    social_text = "\n".join(f"- {a.get_text(strip=True)}: {a['href']}" for a in social) or "غير متوفرة"

    info = (
        "🎓 *أكاديمية اكتفاء*\n\n"
        f"📌 *من نحن:*  \n{about_text}\n\n"
        f"💼 *الدورات التدريبية:*  \n{courses_text}\n\n"
        f"📲 *وسائل التواصل:*  \n{social_text}\n\n"
        "🌐 *الموقع الرسمي:* https://ektifa.academy/"
    )
    return info

# --- معالج الرسائل ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text or ""
    user_id      = update.effective_user.id

    if "اكتفاء" in user_message.lower() or "ektifa" in user_message.lower():
        reply = fetch_ektifa_info()
        # شعار الأكاديمية (لو الرابط ثابت)
        logo_url = "https://ektifa.academy/_next/image?url=%2Flogo.png&w=256&q=75"
        await update.message.reply_photo(photo=logo_url, caption=reply, parse_mode="Markdown")
    else:
        completion = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "أجب كأنك موظف في أكاديمية اكتفاء، بإيجاز ووضوح وبأسلوب ودود."},
                {"role": "user",   "content": user_message},
            ]
        )
        reply = completion.choices[0].message.content
        await update.message.reply_text(reply)

    # حفظ المحادثة
    chat_collection.insert_one({
        "user_id": user_id,
        "message": user_message,
        "reply":   reply
    })

# --- معالج /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE)

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- نقطة النهاية للويب هوك ---
@web_app.route("/webhook", methods=["POST"])
async def webhook():
    data = await request.get_json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return "OK"

# --- التشغيل المتزامن للبوت والخادم ---
async def main():
    await telegram_app.initialize()
    await telegram_app.start()
    await web_app.run_task(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    asyncio.run(main())
