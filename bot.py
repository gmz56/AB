import os
import json
import logging
import yt_dlp
from threading import Thread
from flask import Flask, render_template_string, request, jsonify, send_file
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, InlineQueryHandler, filters, ContextTypes

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
        'format': 'best[ext=mp4]/best' if format_type != "audio_only" else 'bestaudio/best',
    }

    if format_type == "audio_only":
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }]

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
    <title>مُحمّل الميديا ⚡️</title>
    <style>
        body { background: #0d1117; color: #fff; font-family: sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .card { background: #161b22; padding: 30px; border-radius: 15px; text-align: center; width: 90%; max-width: 400px; }
        input, button { width: 100%; padding: 12px; margin-top: 10px; border-radius: 8px; border: none; box-sizing: border-box; }
        button { background: #00f2fe; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
<div class="card">
    <h2>🚀 التحميل المباشر ⚡️</h2>
    <input type="url" id="url" placeholder="ضع الرابط هنا...">
    <button onclick="dl()">تحميل</button>
</div>
<script>
function dl(){
    const u = document.getElementById('url').value;
    if(!u) return alert('أدخل رابطاً!');
    fetch('/download', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url:u, format_type:'video_best'})})
    .then(r=>r.blob()).then(b=>{
        const a = document.createElement('a');
        a.href = URL.createObjectURL(b);
        a.download = "video.mp4";
        a.click();
    });
}
</script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/download', methods=['POST'])
def web_download():
    data = request.get_json()
    try:
        file_path = download_media(data.get('url'), data.get('format_type', 'video_best'))
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
    welcome_text = "أهلاً بك! أرسل لي أي رابط وسأقوم بتحميله لك فوراً ⚡️"
    keyboard = [
        [InlineKeyboardButton("🔍 جرب التحميل السريع", switch_inline_query="")],
        [InlineKeyboardButton("🧞‍♂️ الجني الأزرق (@WeWillRevise_bot)", url="https://t.me/WeWillRevise_bot")],
        [InlineKeyboardButton("🌐 المنصة الإلكترونية", url="https://ab-rbx9.onrender.com")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"):
        return await update.message.reply_text("أرسل رابطاً صحيحاً 🔗")
    
    user_urls[update.effective_user.id] = url
    
    # قائمة الأزرار مع إضافة زر الجني الأزرق
    keyboard = [
        [InlineKeyboardButton("⚡️ تحميل فيديو مباشر", callback_data="video_best")],
        [InlineKeyboardButton("🧞‍♂️ الجني الأزرق - @WeWillRevise_bot", url="https://t.me/WeWillRevise_bot")]
    ]
    
    message_text = (
        "🎉 **اختر خيار التحميل أو افتح البوت الأخر:**\n\n"
        "🤖 **@WeWillRevise_bot — الجني الازرق**\n\n"
        "👇 افتحه الان من الزر ادناه."
    )
    
    await update.message.reply_text(message_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    url = user_urls.get(query.from_user.id)
    if not url:
        return await query.edit_message_text("انتهت الجلسة، أرسل الرابط مجدداً.")
    
    await query.edit_message_text("⏳ جاري التحميل...")
    try:
        file_path = download_media(url, query.data)
        with open(file_path, 'rb') as f:
            await context.bot.send_video(chat_id=query.message.chat_id, video=f, supports_streaming=True)
        await query.message.reply_text("✅ تم التحميل بنجاح!")
    except Exception as e:
        await query.message.reply_text(f"❌ حدث خطأ: {e}")
    finally:
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)

def main():
    Thread(target=run_flask_site, daemon=True).start()
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN: raise ValueError("TELEGRAM_BOT_TOKEN غير متوفر!")
    
    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot_app.add_handler(CallbackQueryHandler(button_click))
    bot_app.run_polling()

if __name__ == "__main__":
    main()
