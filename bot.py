import os
import logging
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, InlineQueryHandler, filters, ContextTypes
from media import download_media, app as flask_app

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def run_flask_site():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host='0.0.0.0', port=port, use_reloader=False)

user_urls = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "أهلاً بك في بوت التحميل الشامل السريع! ⚡️🚀\n\n"
        "أرسل لي أي رابط الآن (TikTok, YouTube, Instagram) وسأقوم بتحميله فوراً دون انتظار!"
    )

    keyboard = [
        [InlineKeyboardButton("🔍 جرب التحميل السريع (Inline)", switch_inline_query="")],
        [InlineKeyboardButton("🌐 زيارة المنصة الإلكترونية", url="https://ab-rbx9.onrender.com")],
        [InlineKeyboardButton("💡 طريقة الاستخدام", callback_data="how_to_use")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("الرجاء إرسال رابط صحيح يبتدئ بـ http أو https 🔗")
        return

    user_id = update.effective_user.id
    user_urls[user_id] = url

    # خيارات سريعة فورية بدون جلب معاينة بطيئة
    keyboard = [
        [InlineKeyboardButton("⚡️ تحميل فيديو مباشر", callback_data="video_best")],
        [InlineKeyboardButton("🎵 تحميل صوت فقط (MP3)", callback_data="audio_only")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⚡️ **اختر طريقة التحميل الفورية:**", reply_markup=reply_markup, parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "how_to_use":
        instructions = (
            "📖 **طريقة الاستخدام السريعة:**\n\n"
            "فقط أرسل الرابط واختر تحميل مباشر، وسيرسل لك الفيديو في ثوانٍ!"
        )
        await query.message.reply_text(instructions, parse_mode="Markdown")
        return

    user_id = query.from_user.id
    url = user_urls.get(user_id)

    if not url:
        await query.edit_message_text("❌ انتهت الجلسة. يرجى إرسال الرابط من جديد.")
        return

    fmt_type = query.data
    await query.edit_message_text("⏳ **جاري التنزيل والرفع بأقصى سرعة...**")

    file_result = None
    try:
        file_result = download_media(url, format_type=fmt_type)

        if isinstance(file_result, list):
            media_group = [InputMediaPhoto(open(img, 'rb')) for img in file_result[:10] if os.path.exists(img)]
            if media_group:
                await context.bot.send_media_group(chat_id=query.message.chat_id, media=media_group)
        else:
            with open(file_result, 'rb') as f:
                if fmt_type == "audio_only":
                    await context.bot.send_audio(chat_id=query.message.chat_id, audio=f)
                else:
                    await context.bot.send_video(chat_id=query.message.chat_id, video=f, supports_streaming=True)

        await query.message.reply_text("✅ **تم التحميل بنجاح خارق!**")

    except Exception as e:
        logger.error(f"Telegram Error: {e}")
        await query.message.reply_text(f"❌ حدث خطأ أثناء التحميل: {e}")
    finally:
        if isinstance(file_result, list):
            for f in file_result:
                if os.path.exists(f): os.remove(f)
        elif file_result and os.path.exists(file_result):
            os.remove(file_result)

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query or not query.startswith("http"):
        return

    results = [
        InlineQueryResultArticle(
            id="1",
            title="رابط تحميل الميديا جاهز 🚀",
            description="اضغط هنا لإرسال رابط التحميل المباشر",
            input_message_content=InputTextMessageContent(f"حمل هذا المقطع فوراً عبر البوت:\n{query}")
        )
    ]
    await update.inline_query.answer(results)

def main():
    server_thread = Thread(target=run_flask_site)
    server_thread.daemon = True
    server_thread.start()

    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN غير متوفر!")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(InlineQueryHandler(inline_query_handler))
    
    app.run_polling()

if __name__ == "__main__":
    main()
