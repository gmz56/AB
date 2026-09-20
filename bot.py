import os
import json
import logging
import requests
import yt_dlp
from threading import Thread
from flask import Flask, render_template_string, request, jsonify, send_file
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, InlineQueryHandler, filters, ContextTypes

# إعداد السجلات
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------------------------------
# 1️⃣ قسم سيرفر FLASK والموقع الإلكتروني وحساب الإحصائيات
# ----------------------------------------------------
app = Flask(__name__)
COUNTER_FILE = "stats.json"

def get_stats():
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"downloads": 0}

def increment_stats():
    stats = get_stats()
    stats["downloads"] = stats.get("downloads", 0) + 1
    with open(COUNTER_FILE, 'w') as f:
        json.dump(stats, f)
    return stats["downloads"]

def download_media(url, format_type="video_best"):
    increment_stats()
    output_template = 'downloads/%(id)s.%(ext)s'
    os.makedirs('downloads', exist_ok=True)

    ydl_opts = {
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'concurrent_fragment_downloads': 10,
    }

    if format_type == "audio_only":
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }]
    elif format_type == "video_low":
        ydl_opts['format'] = 'worst[ext=mp4]/worst'
    else:
        # استخراج أقصى جودة فور كي وأفضل جودة صوت وفيديو دون ضغط (4K / Ultra HD)
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
        ydl_opts['merge_output_format'] = 'mp4'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if format_type == "audio_only":
            base, _ = os.path.splitext(filename)
            filename = base + ".mp3"
        return filename

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مُحمّل الميديا الخارق 4K ⚡️🤯</title>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        body { background: #0d1117; color: #fff; font-family: 'Tajawal', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
        .card { background: #161b22; border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; padding: 30px; width: 100%; max-width: 450px; text-align: center; box-shadow: 0 10px 30px rgba(0,242,254,0.15); }
        input, select, button { width: 100%; padding: 14px; margin-top: 12px; border-radius: 10px; border: none; font-size: 1rem; box-sizing: border-box; }
        input { background: #0d1117; color: #fff; border: 1px solid #30363d; }
        button { background: linear-gradient(135deg, #00f2fe, #4facfe); color: #000; font-weight: bold; cursor: pointer; transition: 0.3s; }
        button:hover { transform: scale(1.02); }
    </style>
</head>
<body>
<div class="card">
    <h1>🚀 التحميل السريع بجودة 4K 🤯</h1>
    <p>أدخل الرابط واحصل على أقصى دقة وفول إتش دي فوراً</p>
    <input type="url" id="url" placeholder="أدخل الرابط هنا...">
    <select id="fmt">
        <option value="video_best">🔥 فيديو خارق 4K Full HD</option>
        <option value="audio_only">🎵 صوت بأعلى نقاء (320Kbps MP3)</option>
    </select>
    <button onclick="dl()">⚡️ تحميل مجنون فوراً</button>
</div>
<script>
function dl(){
    const u = document.getElementById('url').value;
    const f = document.getElementById('fmt').value;
    if(!u) return alert('ضع رابطاً!');
    fetch('/download', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url:u, format_type:f})})
    .then(r=>r.blob()).then(b=>{
        const a = document.createElement('a');
        a.href = URL.createObjectURL(b);
        a.download = "media_4k";
        a.click();
    });
}
</script>
</body>
</html>
"""

@app.route('/')
def home():
    stats = get_stats()
    return render_template_string(HTML_TEMPLATE, downloads=stats["downloads"])

@app.route('/download', methods=['POST'])
def web_download():
    data = request.get_json()
    url = data.get('url')
    fmt = data.get('format_type', 'video_best')
    try:
        file_path = download_media(url, format_type=fmt)
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

def run_flask_site():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# ----------------------------------------------------
# 2️⃣ قسم بوت تليجرام (Telegram Bot Logic)
# ----------------------------------------------------
user_urls = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "أهلاً بك في بوت التحميل المجنون والشامل! ⚡️🤯🔥\n\n"
        "أرسل لي أي رابط (TikTok, YouTube, Instagram) وسأقوم بتحميله بأعلى جودة 4K وبالمقاس الطولي المثالي!"
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

    keyboard = [
        [InlineKeyboardButton("🔥 تحميل فيديو 4K Full HD", callback_data="video_best")],
        [InlineKeyboardButton("🎵 تحميل صوت بأعلى نقاء (MP3 320k)", callback_data="audio_only")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⚡️ **اختر الجودة المطلوبة للتحميل:**", reply_markup=reply_markup, parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "how_to_use":
        instructions = (
            "📖 **طريقة الاستخدام السريعة:**\n\n"
            "فقط أرسل الرابط واختر الجودة الخارقة، وسيرسل لك الفيديو بمقاس الشاشة الطولي وبجودة عالية جداً!"
        )
        await query.message.reply_text(instructions, parse_mode="Markdown")
        return

    user_id = query.from_user.id
    url = user_urls.get(user_id)

    if not url:
        await query.edit_message_text("❌ انتهت الجلسة. يرجى إرسال الرابط من جديد.")
        return

    fmt_type = query.data
    await query.edit_message_text("⏳ **جاري التنزيل والمعالجة بأعلى جودة 4K... 🚀**")

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
                    await context.bot.send_video(
                        chat_id=query.message.chat_id,
                        video=f,
                        supports_streaming=True
                    )

        await query.message.reply_text("✅ **تم التحميل بجودة خارقة ومجنونة! 🤯🔥**")

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
            title="رابط تحميل الميديا جاهز (4K) 🚀",
            description="اضغط هنا لإرسال رابط التحميل المباشر",
            input_message_content=InputTextMessageContent(f"حمل هذا المقطع فوراً بأعلى جودة عبر البوت:\n{query}")
        )
    ]
    await update.inline_query.answer(results)

# ----------------------------------------------------
# 3️⃣ التشغيل الرئيسي (Main Execution)
# ----------------------------------------------------
def main():
    server_thread = Thread(target=run_flask_site)
    server_thread.daemon = True
    server_thread.start()

    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN غير متوفر!")

    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot_app.add_handler(CallbackQueryHandler(button_click))
    bot_app.add_handler(InlineQueryHandler(inline_query_handler))
    
    bot_app.run_polling()

if __name__ == "__main__":
    main()
