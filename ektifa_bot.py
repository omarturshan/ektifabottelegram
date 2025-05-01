import os
import logging
from quart import Quart, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from zenrows import ZenRowsClient

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ZENROWS_API_KEY = os.environ["ZENROWS_API_KEY"]
BASE_URL = os.environ["RENDER_EXTERNAL_URL"]

# إعداد البوت و ZenRows
client = ZenRowsClient(ZENROWS_API_KEY)
app = Quart(__name__)
application = Application.builder().token(TOKEN).build()

# استخلاص المعلومات من موقع اكتفاء
async def fetch_ektifa_info():
    url = "https://ektifa-academy.com/"
    params = {"js_render": "true"}
    response = client.get(url, params=params)
    if response.status_code == 200:
        return response.text[:3900]  # تجنب تجاوز حد التليجرام
    else:
        return "⚠️ لم أستطع الوصول إلى موقع الأكاديمية حالياً."

# الرد على الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "اكتفاء" in text or "ektifa" in text:
        reply = await fetch_ektifa_info()
        await update.message.reply_text(reply)
    else:
        await update.message.reply_text("مرحباً! اسألني عن أكاديمية اكتفاء 🌟")

# إضافة المعالجات
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Webhook endpoint
@app.post("/webhook")
async def webhook():
    data = await request.get_json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return "ok"

# إعداد Webhook
@app.before_serving
async def setup_webhook():
    webhook_url = f"{BASE_URL}/webhook"
    await application.bot.set_webhook(webhook_url)

# تشغيل التطبيق
if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(app.run_task(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))))
