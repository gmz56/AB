import os
import time
import logging
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from media import download_media

# 1. إعداد خادم Flask وهمي لإرضاء متطلبات Render Web Service
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot is running live!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# 2. إعداد التسجيل (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# أمر /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "أهلاً بك! 🖐️\n"
        "أرسل لي أي رابط فيديو (يوتيوب، تيك توك، إنستغرام...) وسأقوم بتحميله لك بأعلى جودة ممكنة! 🚀"
    )
    await update.message.reply_text(welcome_text)

# معالجة الروابط المرسلة
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("الرجاء إرسال رابط صحيح يبتدئ بـ http أو https 🔗")
        return

    status_msg = await update.message.reply_text("⏳ جاري البدء في التحميل...")
    last_update_time = [0]

    def progress_callback(percent, speed):
        current_time = time.time()
        if current_time - last_update_time[0] > 3.5:
            last_update_time[0] = current_time
            bar_length = 10
            filled_length = int(bar_length * percent // 100)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            
            text = (
                f"⏳ **جاري التحميل...**\n\n"
                f"[{bar}] {percent:.1f}%\n"
                f"🚀 **السرعة:** {speed}"
            )
            try:
                context.application.create_task(
                    status_msg.edit_text(text, parse_mode='Markdown')
                )
            except Exception:
                pass

    file_path = None
    try:
        file_path = download_media(url, progress_callback)
        await status_msg.edit_text("📤 جاري رفع الفيديو إليك بأعلى جودة...")

        with open(file_path, 'rb') as video_file:
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=video_file,
                supports_streaming=True,
                caption="✅ تم التحميل بنجاح بأعلى جودة ممتازة!"
            )
        
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Error during download/send: {e}")
        await status_msg.edit_text(f"❌ حدث خطأ أثناء التحميل: {e}")

    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"🧹 تم حذف الملف المؤقت بنجاح: {file_path}")
            except Exception as cleanup_err:
                logger.error(f"فشل حذف الملف المؤقت: {cleanup_err}")

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("يرجى ضبط متغير البيئة TELEGRAM_BOT_TOKEN!")

    # تشغيل خادم Flask في الخفاء
    Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 البوت يعمل الآن بنجاح...")
    app.run_polling()

if __name__ == "__main__":
    main()
