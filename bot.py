import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from media import download_media

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# تخزين مؤقت للروابط
user_urls = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "أهلاً بك في بوت التحميل الشامل! 🚀\n\n"
        "يدعم التحميل من:\n"
        "• تيك توك (فيديوهات وألبومات صور)\n"
        "• يوتيوب • إنستغرام • سناب شات • إكس\n\n"
        "فقط أرسل لي أي رابط وسأقوم بتجهيزه لك فوراً!"
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("الرجاء إرسال رابط صحيح يبتدئ بـ http أو https 🔗")
        return

    user_id = update.effective_user.id
    user_urls[user_id] = url

    keyboard = [
        [InlineKeyboardButton("🎬 فيديو أعلى جودة", callback_data="video_best")],
        [InlineKeyboardButton("📱 فيديو جودة متوسطة", callback_data="video_low")],
        [InlineKeyboardButton("🎵 صوت فقط (MP3)", callback_data="audio_only")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر نوع التحميل المطلوب:", reply_markup=reply_markup)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    url = user_urls.get(user_id)

    if not url:
        await query.edit_message_text("❌ انتهت الجلسة. يرجى إرسال الرابط من جديد.")
        return

    fmt_type = query.data
    await query.edit_message_text("⏳ جاري جلب وتحميل المحتوى...")

    file_result = None
    try:
        file_result = download_media(url, format_type=fmt_type)

        if isinstance(file_result, list):
            await query.message.reply_text(f"📸 جاري رفع ألبوم يحتوي على {len(file_result)} صورة...")
            media_group = []
            for img_path in file_result[:10]:
                if os.path.exists(img_path):
                    media_group.append(InputMediaPhoto(open(img_path, 'rb')))
            
            if media_group:
                await context.bot.send_media_group(chat_id=query.message.chat_id, media=media_group)
        else:
            await query.message.reply_text("📤 جاري رفع الملف إليك...")
            with open(file_result, 'rb') as f:
                if fmt_type == "audio_only":
                    await context.bot.send_audio(chat_id=query.message.chat_id, audio=f)
                else:
                    await context.bot.send_video(chat_id=query.message.chat_id, video=f, supports_streaming=True)

        share_kb = [[InlineKeyboardButton("🔗 مشاركة البوت مع صديق", switch_inline_query="جرب هذا البوت الممتاز للتحميل!")]]
        await query.message.reply_text("🎉 تم التحميل بنجاح!", reply_markup=InlineKeyboardMarkup(share_kb))

    except Exception as e:
        logger.error(f"Telegram Error: {e}")
        await query.message.reply_text(f"❌ حدث خطأ أثناء التحميل: {e}")
    finally:
        if isinstance(file_result, list):
            for f in file_result:
                if os.path.exists(f): os.remove(f)
        elif file_result and os.path.exists(file_result):
            os.remove(file_result)

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN غير متوفر!")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))
    app.run_polling()

if __name__ == "__main__":
    main()
