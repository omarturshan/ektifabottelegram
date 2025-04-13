import os
import requests
from quart import Quart, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from pymongo import MongoClient
from bs4 import BeautifulSoup

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

# دالة لجلب معلومات الأكاديمية من الموقع
def get_ektifa_info():
    url = "https://ektifa.academy/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    
    # استخراج المعلومات من الصفحة
    # هذه الأمثلة يجب أن تتكيف مع الهيكل الفعلي للموقع
    about_section = soup.find("section", {"id": "about"})  # تحديد قسم "من نحن"
    courses_section = soup.find("section", {"id": "courses"})  # قسم الدورات
    contact_section = soup.find("section", {"id": "contact"})  # قسم التواصل

    # استخلاص النصوص من الأقسام
    about_text = about_section.get_text(strip=True) if about_section else "معلومات عن الأكاديمية غير متوفرة."
    courses_text = courses_section.get_text(strip=True) if courses_section else "الدورات التدريبية غير متوفرة."
    contact_text = contact_section.get_text(strip=True) if contact_section else "بيانات التواصل غير متوفرة."

    # تحضير النص النهائي للرد
    info = (
        "🎓 *أكاديمية اكتفاء*\n\n"
        f"📌 *من نحن:*\n{about_text}\n\n"
        f"💼 *الدورات التدريبية:*\n{courses_text}\n\n"
        f"📲 *وسائل التواصل:*\n{contact_text}\n\n"
        "🌐 *الموقع الرسمي:* https://ektifa.academy/"
    )
    
    return info

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.effective_user.id

    # تحقق إذا الرسالة تتعلق بأكاديمية اكتفاء
    if any(word in user_message.lower() for word in ["اكتفاء", "ektifa"]):
        reply = get_ektifa_info()  # جلب معلومات الأكاديمية من الموقع

        logo_url = "https://ektifa.academy/images/logo.png"  # شعار الأكاديمية
        await update.message.reply_photo(photo=logo_url, caption=reply, parse_mode="Markdown")
    else:
        # إرسال السؤال إلى OpenAI
        completion = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "أجب كأنك موظف في أكاديمية اكتفاء، بإيجاز ووضوح وبأسلوب ودود."},
                {"role": "user", "content": user_message},
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
