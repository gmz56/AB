import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from media import download_media

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! أرسل لي رابط فيديو من TikTok أو YouTube وسأقوم بتحميله لك مباشرة.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("يرجى إرسال رابط صحيح.")
        return

    status_msg = await update.message.reply_text("جاري تحميل الفيديو، يرجى الانتظار...")

    try:
        file_path = download_media(url)
        with open(file_path, 'rb') as video:
            await update.message.reply_video(video=video)
        await status_msg.delete()
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.edit_text("حدث خطأ أثناء تحميل الفيديو. تأكد من صحة الرابط وحاول مرة أخرى.")

def main():
    if not TOKEN:
        print("خطأ: لم يتم العثور على TELEGRAM_BOT_TOKEN في متغيرات البيئة!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("البوت يعمل الآن...")
    app.run_polling()

if __name__ == '__main__':
    main()
