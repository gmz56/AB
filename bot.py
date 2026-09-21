import os
import json
import logging
import gc
import yt_dlp
from threading import Thread
from flask import Flask, render_template_string, request, jsonify, send_file
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------------------------------
# 1️⃣ قسم إدارة البيانات وحفظ المستخدمين والصيانة
# ----------------------------------------------------
app = Flask(__name__)
COUNTER_FILE = "stats.json"
USERS_FILE = "users.json"
MAINTENANCE_FILE = "maintenance.json"

ADMIN_ID = os.getenv("ADMIN_ID") # يمكنك وضع آيدي حسابك في متغيرات البيئة بـ Render

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

def get_all_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return []

def toggle_maintenance():
    current = is_maintenance()
    with open(MAINTENANCE_FILE, 'w') as f:
        json.dump({"maintenance": not current}, f)
    return not current

def is_maintenance():
    if os.path.exists(MAINTENANCE_FILE):
        try:
            with open(MAINTENANCE_FILE, 'r') as f:
                return json.load(f).get("maintenance", False)
        except:
            pass
    return False

def clean_url(url):
    clean = url.split("?")[0].strip()
    if "tiktok.com" in clean and "/photo/" in clean:
        clean = clean.replace("/photo/", "/video/")
    return clean

def detect_platform(url):
    u = url.lower()
    if "tiktok.com" in u:
        return "🎵 تيك توك (TikTok)"
    elif "instagram.com" in u:
        return "📸 إنستغرام (Instagram)"
    elif "youtube.com" in u or "youtu.be" in u:
        return "🔴 يوتيوب (YouTube)"
    elif "twitter.com" in u or "x.com" in u:
        return "🐦 تويتر / X"
    return "🌐 منصة إلكترونية"

def download_media(url, format_type="video_best"):
    increment_stats()
    os.makedirs('downloads', exist_ok=True)
    target_url = clean_url(url)
    
    # اختيار أعلى جودة أصلية ممكنة
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'format': 'best[ext=mp4][filesize<50M]/bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[filesize<50M]/best',
        'max_filesize': 50 * 1024 * 1024,
        'merge_output_format': 'mp4',
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
        return filename

# ----------------------------------------------------
# 2️⃣ سيرفر Web / Flask
# ----------------------------------------------------
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
    file_path = None
    try:
        file_path = download_media(data.get('url'), data.get('format_type', 'video_best'))
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        if file_path and os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        gc.collect()

def run_flask_site():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# ----------------------------------------------------
# 3️⃣ قسم بوت تليجرام (Telegram Bot Engine)
# ----------------------------------------------------
user_urls = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    if is_maintenance() and str(user_id) != str(ADMIN_ID):
        return await update.message.reply_text("🛠 **البوت يخضع لتحديثات وصيانة سريعة حالياً.**\nيرجى المحاولة بعد قليل ⚡️", parse_mode="Markdown")

    welcome_text = "أهلاً بك! أرسل لي أي رابط (تيك توك، إنستغرام، يوتيوب، تويتر) وسأقوم بتحميله لك بأعلى جودة أصلية ⚡️"
    keyboard = [
        [InlineKeyboardButton("🔍 جرب التحميل السريع", switch_inline_query="")],
        [InlineKeyboardButton("🌐 المنصة الإلكترونية", url="https://ab-rbx9.onrender.com")]
    ]
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_stats()
    users_count = len(get_all_users())
    await update.message.reply_text(
        f"📊 **إحصائيات البوت:**\n\n"
        f"👥 عدد المستخدمين: `{users_count}`\n"
        f"📥 إجمالي التحميلات: `{stats.get('downloads', 0)}`",
        parse_mode="Markdown"
    )

async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if ADMIN_ID and user_id != str(ADMIN_ID):
        return await update.message.reply_text("❌ هذا الأمر مخصص لمالك البوت فقط.")
    
    status = toggle_maintenance()
    txt = "🛠 تم **تفعيل** وضع الصيانة وإيقاف البوت عن المستخدمين." if status else "✅ تم **إلغاء** وضع الصيانة وإعادة تشغيل البوت للجميع."
    await update.message.reply_text(txt, parse_mode="Markdown")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if ADMIN_ID and user_id != str(ADMIN_ID):
        return await update.message.reply_text("❌ هذا الأمر مخصص لمالك البوت فقط.")
    
    msg_to_send = " ".join(context.args)
    if not msg_to_send:
        return await update.message.reply_text("💡 اكتب الرسالة بعد الأمر كالتالي:\n`/broadcast أهلاً بكم في التحديث الجديد`", parse_mode="Markdown")
    
    users = get_all_users()
    success, failed = 0, 0
    await update.message.reply_text(f"📢 جاري إرسال الإذاعة إلى {len(users)} مستخدم...")
    
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=msg_to_send)
            success += 1
        except:
            failed += 1
            
    await update.message.reply_text(f"✅ اكتملت الإذاعة!\n\nتم الإرسال لـ: {success}\nفشل الإرسال لـ: {failed}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    if is_maintenance() and str(user_id) != str(ADMIN_ID):
        return await update.message.reply_text("🛠 **البوت يخضع لتحديثات وصيانة سريعة حالياً.**\nيرجى المحاولة بعد قليل ⚡️", parse_mode="Markdown")

    url = update.message.text.strip()
    if not url.startswith("http"):
        return await update.message.reply_text("يرجى إرسال رابط صحيح يبدأ بـ http 🔗")
    
    user_urls[user_id] = url
    platform_name = detect_platform(url)
    
    keyboard = [
        [InlineKeyboardButton("🎬 تحميل فيديو MP4 بأعلى جودة", callback_data="video_best")],
        [InlineKeyboardButton("🎵 تحميل صوت فقط MP3", callback_data="audio_only")]
    ]
    
    message_text = f"📍 **المنصة المكتشفة:** {platform_name}\n\n🎉 **اختر صيغة التحميل:**"
    await update.message.reply_text(message_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    url = user_urls.get(user_id)
    if not url:
        return await query.edit_message_text("انتهت الجلسة، يرجى إرسال الرابط مجدداً.")
    
    # تحديث النص لبدء التحميل
    await query.edit_message_text("⏳ جاري سحب المقطع بأعلى جودة...")
    file_path = None
    try:
        file_path = download_media(url, query.data)
        
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > 50:
            await query.message.reply_text("⚠️ حجم الملف أكبر من 50 ميجابايت، وهو الحد الأقصى المسموح به في تليجرام.")
            return

        caption_text = "✅ تم التحميل بأعلى جودة أصلية بواسطة بوت التحميل ⚡️"
        
        # إرسال الملف
        if query.data == "audio_only":
            await context.bot.send_audio(chat_id=query.message.chat_id, audio=open(file_path, 'rb'), caption=caption_text)
        else:
            await context.bot.send_video(chat_id=query.message.chat_id, video=open(file_path, 'rb'), supports_streaming=True, caption=caption_text)
        
        # ميزة تنظيف المحادثة تلقائياً: حذف رسالة الإنتظار القديمة
        try:
            await query.message.delete()
        except:
            pass

    except Exception as e:
        logger.error(f"Error during download: {e}")
        await query.message.reply_text("❌ تعذر تحميل المقطع. تأكد أن الرابط يعمل والحساب ليس خاصاً (Private).")
    finally:
        user_urls.pop(user_id, None)
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        gc.collect()

def main():
    Thread(target=run_flask_site, daemon=True).start()
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN: raise ValueError("TELEGRAM_BOT_TOKEN غير متوفر!")
    
    bot_app = Application.builder().token(TOKEN).build()
    
    # الأوامر الرئيسية
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("stats", stats_command))
    bot_app.add_handler(CommandHandler("broadcast", broadcast_command))
    bot_app.add_handler(CommandHandler("maintenance", maintenance_command))
    
    # التعامل مع الرسائل والأزرار
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot_app.add_handler(CallbackQueryHandler(button_click))
    
    bot_app.run_polling()

if __name__ == "__main__":
    main()
