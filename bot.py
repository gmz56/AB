import os
import json
import logging
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
        'concurrent_fragment_downloads': 1,
    }

    if format_type == "audio_only":
        # صوت نقّي بدون تقطيع بنمط تيك توك الأصلي
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        ydl_opts['postprocessor_args'] = [
            '-ar', '44100',
        ]
    else:
        # إزالة التبطيء والتقطيع نهائياً عبر ضبط جودة الفيديو وتوحيد معدل الإطارات بترميز H.264 و AAC
        ydl_opts['format'] = 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/b/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }]
        ydl_opts['postprocessor_args'] = [
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-preset', 'ultrafast',  # سرعة فائقة لمنع إجهاد السيرفر وحفظ جميع الإطارات
            '-c:a', 'aac',
            '-b:a', '192k',
            '-ar', '44100',
        ]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        
        # التأكد من الامتداد الصحيح عند التحويل
        if format_type == "audio_only":
            base, _ = os.path.splitext(filename)
            filename = base + ".mp3"
        else:
            base, _ = os.path.splitext(filename)
            filename = base + ".mp4"
            
        return filename

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مُحمّل الميديا السريع ⚡️</title>
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
    <h1>🚀 التحميل المباشر الناعم ⚡️</h1>
    <p>تحميل سريع بدون بطء أو تقطيع في الفيديو 🎬🎵</p>
    <input type="url" id="url" placeholder="أدخل الرابط هنا...">
    <select id="fmt">
        <option value="video_best">🎬 فيديو سلس بدون تبطيء (H.264 / AAC)</option>
        <option value="audio_only">🎵 صوت فقط بنمط تيك توك (MP3 192k)</option>
    </select>
    <button onclick="dl()">⚡️ تحميل</button>
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
        a.download = "smooth_video";
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
    welcome_text = "أهلاً بك! أرسل لي أي رابط وسأقوم بتحميله بسلاسة فائقة وبدون أي تقطيع أو تبطيء في الفيديو ⚡️🎬🎵"
    keyboard = [
        [InlineKeyboardButton("🔍 جرب التحميل السريع", switch_inline_query="")],
        [InlineKeyboardButton("🌐 المنصة الإلكترونية", url="https://ab-rbx9.onrender.com")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("الرجاء إرسال رابط صحيح 🔗")
        return

    user_id = update.effective_user.id
    user_urls[user_id] = url

    keyboard = [
        [InlineKeyboardButton("⚡️ تحميل فيديو سلس (إزالة التبطيء)", callback_data="video_best")],
        [InlineKeyboardButton("🎵 تحميل صوت فقط (MP3 تيك توك)", callback_data="audio_only")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⚡️ **اختر الخيار المناسب:**", reply_markup=reply_markup, parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    url = user_urls.get(user_id)

    if not url:
        await query.edit_message_text("❌ انتهت الجلسة. أرسل الرابط مجدداً.")
        return

    fmt_type = query.data
    await query.edit_message_text("⏳ **جاري التنزيل والمعالجة لإزالة أي تقطيع... 🚀**")

    file_result = None
    try:
        file_result = download_media(url, format_type=fmt_type)

        with open(file_result, 'rb') as f:
            if fmt_type == "audio_only":
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=f)
            else:
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=f,
                    supports_streaming=True
                )

        await query.message.reply_text("✅ **تم التحميل بنجاح بسلاسة كاملة وبدون تبطيء! ⚡️**")

    except Exception as e:
        logger.error(f"Telegram Error: {e}")
        await query.message.reply_text(f"❌ حدث خطأ: {e}")
    finally:
        if file_result and os.path.exists(file_result):
            os.remove(file_result)

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query or not query.startswith("http"):
        return

    results = [
        InlineQueryResultArticle(
            id="1",
            title="رابط التحميل المباشر 🚀",
            input_message_content=InputTextMessageContent(f"حمل المقطع عبر البوت:\n{query}")
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
