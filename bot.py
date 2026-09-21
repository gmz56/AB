import os
import json
import logging
import gc
import requests
import time
import base64
import yt_dlp
from threading import Thread
from flask import Flask, render_template_string, request, jsonify, send_file
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
COUNTER_FILE = "stats.json"
USERS_FILE = "users.json"
ADMIN_ID = os.getenv("ADMIN_ID")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# --- إدارة الإحصائيات والمستخدمين ---
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

def save_user(user_id):
    users = set()
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                users = set(json.load(f))
        except:
            pass
    users.add(user_id)
    with open(USERS_FILE, 'w') as f:
        json.dump(list(users), f)

def clean_url(url):
    clean = url.split("?")[0].strip()
    if "tiktok.com" in clean and "/photo/" in clean:
        clean = clean.replace("/photo/", "/video/")
    return clean

# --- معالجة الذكاء الاصطناعي لمسح النصوص (AI Inpainting) ---
def process_ai_inpainting(video_path):
    if not REPLICATE_API_TOKEN:
        logger.warning("لم يتم العثور على REPLICATE_API_TOKEN، سيتم إرجاع الفيديو الأصلي.")
        return video_path

    try:
        headers = {
            "Authorization": f"Token {REPLICATE_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # تشفير الفيديو بـ base64
        with open(video_path, 'rb') as f:
            encoded_video = base64.b64encode(f.read()).decode('utf-8')
        
        upload_req = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers=headers,
            json={
                "version": "bf6398f561b365825d1947b4d1b8f041b6c00d41829e0617300c8f5f4b5f8997",
                "input": {
                    "video": f"data:video/mp4;base64,{encoded_video}"
                }
            }
        )
        
        res_data = upload_req.json()
        prediction_id = res_data.get("id")
        
        if not prediction_id:
            logger.error(f"خطأ في Replicate: {res_data}")
            return video_path

        # الانتظار لحين اكتمال معالجة الذكاء الاصطناعي
        status_url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        for _ in range(60): # أقصى انتظار 2 دقيقة
            time.sleep(2)
            check_res = requests.get(status_url, headers=headers).json()
            status = check_res.get("status")
            
            if status == "succeeded":
                output_url = check_res.get("output")
                if output_url:
                    clean_path = video_path.replace(".mp4", "_clean.mp4")
                    v_data = requests.get(output_url).content
                    with open(clean_path, 'wb') as out_f:
                        out_f.write(v_data)
                    if os.path.exists(video_path):
                        os.remove(video_path)
                    return clean_path
                break
            elif status in ["failed", "canceled"]:
                logger.error("فشلت عملية الذكاء الاصطناعي")
                break

    except Exception as e:
        logger.error(f"خطأ أثناء معالجة AI Inpainting: {e}")
    
    return video_path

# --- تحميل الميديا ---
def download_media(url, format_type="video_best", remove_text=False):
    increment_stats()
    os.makedirs('downloads', exist_ok=True)
    target_url = clean_url(url)
    
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'format': 'best',
        'max_filesize': 50 * 1024 * 1024,
    }

    if format_type == "audio_only":
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(target_url, download=True)
        filename = ydl.prepare_filename(info)
        
        if format_type == "audio_only":
            base, _ = os.path.splitext(filename)
            filename = base + ".mp3"
        elif remove_text and filename.endswith('.mp4'):
            filename = process_ai_inpainting(filename)
            
        return filename

# --- واجهة الويب (HTML) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مُحمّل الميديا ومزيل النصوص بالذكاء الاصطناعي ⚡️</title>
    <style>
        body { background: #0d1117; color: #fff; font-family: 'Segoe UI', system-ui, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .card { background: #161b22; padding: 30px; border-radius: 16px; text-align: center; width: 90%; max-width: 440px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid #30363d; }
        h2 { margin-bottom: 20px; color: #58a6ff; font-size: 20px; }
        input[type="url"] { width: 100%; padding: 14px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #30363d; background: #0d1117; color: #fff; box-sizing: border-box; font-size: 14px; text-align: center; }
        .options { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; text-align: right; font-size: 14px; color: #8b949e; }
        .option-item { display: flex; align-items: center; gap: 10px; background: #21262d; padding: 12px; border-radius: 8px; cursor: pointer; }
        button { width: 100%; padding: 14px; border-radius: 8px; border: none; background: #238636; color: #fff; font-weight: bold; font-size: 16px; cursor: pointer; transition: 0.2s; }
        button:hover { background: #2ea043; }
        #status { margin-top: 15px; font-size: 13px; color: #8b949e; }
    </style>
</head>
<body>
<div class="card">
    <h2>🚀 التحميل والمسح الذكي ⚡️</h2>
    <input type="url" id="url" placeholder="ضع رابط الفيديو هنا...">
    
    <div class="options">
        <label class="option-item">
            <input type="radio" name="fmt" value="video_best" checked>
            <span>🎬 تحميل أصلي (بدون حقوق تيك توك)</span>
        </label>
        <label class="option-item">
            <input type="radio" name="fmt" value="video_ai">
            <span>🤖 مسح كامل للنصوص المدمجة (AI Inpainting)</span>
        </label>
        <label class="option-item">
            <input type="radio" name="fmt" value="audio_only">
            <span>🎵 تحميل الصوت فقط (MP3)</span>
        </label>
    </div>

    <button onclick="dl()">بدء التحميل</button>
    <div id="status"></div>
</div>

<script>
function dl(){
    const u = document.getElementById('url').value;
    const statusDiv = document.getElementById('status');
    if(!u) return alert('يرجى إدخال رابط صحيح!');
    
    const selectedOption = document.querySelector('input[name="fmt"]:checked').value;
    let formatType = 'video_best';
    let removeText = false;

    if(selectedOption === 'video_ai') {
        formatType = 'video_best';
        removeText = true;
        statusDiv.innerText = "🤖 جاري معالجة الفيديو بالذكاء الاصطناعي ومسح النصوص (قد يستغرق لحظات)...";
    } else if(selectedOption === 'audio_only') {
        formatType = 'audio_only';
        statusDiv.innerText = "⏳ جاري استخراج الصوت...";
    } else {
        statusDiv.innerText = "⏳ جاري التحميل المباشر...";
    }

    fetch('/download', {
        method: 'POST', 
        headers: {'Content-Type': 'application/json'}, 
        body: JSON.stringify({url: u, format_type: formatType, remove_text: removeText})
    })
    .then(r => {
        if(!r.ok) throw new Error("تعذر معالجة الرابط");
        return r.blob();
    })
    .then(b => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(b);
        a.download = (formatType === 'audio_only') ? "audio.mp3" : "video.mp4";
        a.click();
        statusDiv.innerText = "✅ تم التحميل بنجاح!";
    })
    .catch(err => {
        statusDiv.innerText = "❌ حدث خطأ، يرجى التأكد من الرابط والمحاولة مجدداً.";
    });
}
</script>
</body>
</html>
"""

# --- مسارات Flask ---
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/download', methods=['POST'])
def web_download():
    data = request.get_json()
    file_path = None
    try:
        url = data.get('url')
        fmt = data.get('format_type', 'video_best')
        remove_txt = data.get('remove_text', False)
        
        file_path = download_media(url, format_type=fmt, remove_text=remove_txt)
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        logger.error(f"Web Download Error: {e}")
        return jsonify({'error': str(e)}), 400
    finally:
        if file_path and os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        gc.collect()

def run_flask_site():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# --- أوامر بوت تليجرام ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user.id)
    await update.message.reply_text("أهلاً بك! أرسل رابط الفيديو للتحميل المباشر، أو استخدم الموقع للتحميل مع ميزة مسح النصوص بالذكاء الاصطناعي ⚡️")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    url = update.message.text
    if not url.startswith("http"):
        return
    
    msg = await update.message.reply_text("⏳ جاري التحميل...")
    try:
        file_path = download_media(url, format_type="video_best")
        with open(file_path, 'rb') as video:
            await update.message.reply_video(video=video, caption="تم التحميل بنجاح ⚡️")
        await msg.delete()
        os.remove(file_path)
    except Exception as e:
        await msg.edit_text("❌ تعذر تحميل المقطع.")

def main():
    Thread(target=run_flask_site, daemon=True).start()
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN: raise ValueError("TELEGRAM_BOT_TOKEN غير متوفر!")
    
    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    bot_app.run_polling()

if __name__ == "__main__":
    main()
