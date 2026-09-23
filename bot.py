import os
import json
import logging
import time
import subprocess
import yt_dlp
import base64
from io import BytesIO
from threading import Thread
from flask import Flask, send_from_directory, render_template_string, request, jsonify
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# التحقق من وجود مكتبة PIL لصناعة البطاقات والصور
try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# إعدادات السجلات Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# مجلد التخزين المؤقت
UPLOAD_FOLDER = 'temp_uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ==========================================
# 1. إعداد سيرفر Flask والموقع التفاعلي المباشر
# ==========================================
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>منصة سلنقح | التحميل والتوضيح المباشر 🇸🇦</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800;900&display=swap" rel="stylesheet">
    <style>
        * { font-family: 'Cairo', sans-serif; }
        body {
            background: linear-gradient(135deg, #0a1f14 0%, #05100a 100%);
            color: #ffffff;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header-section {
            padding: 40px 20px 20px;
            text-align: center;
        }
        .brand-badge {
            background: rgba(25, 135, 84, 0.2);
            border: 1px solid #198754;
            color: #2ecc71;
            padding: 6px 18px;
            border-radius: 50px;
            font-size: 0.9rem;
            display: inline-block;
            margin-bottom: 15px;
        }
        .hero-title {
            font-size: 2.2rem;
            font-weight: 900;
            background: linear-gradient(45deg, #2ecc71, #ffffff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .tool-card {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 30px;
            backdrop-filter: blur(10px);
            margin-bottom: 30px;
        }
        .nav-pills .nav-link {
            color: #a0aec0;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            margin: 0 5px;
            font-weight: 700;
            padding: 10px 20px;
        }
        .nav-pills .nav-link.active {
            background-color: #198754 !important;
            color: white !important;
        }
        .form-control {
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: white !important;
            border-radius: 12px;
            padding: 12px 18px;
        }
        .form-control:focus {
            background: rgba(0, 0, 0, 0.6);
            border-color: #2ecc71;
            box-shadow: 0 0 10px rgba(46, 204, 113, 0.3);
        }
        .btn-green {
            background: #198754;
            color: white;
            font-weight: 700;
            padding: 12px 28px;
            border-radius: 12px;
            border: none;
            transition: all 0.3s ease;
        }
        .btn-green:hover {
            background: #146c43;
            color: white;
        }
        .spinner-border {
            width: 1.5rem;
            height: 1.5rem;
        }
        footer {
            margin-top: auto;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            padding: 20px 0;
            text-align: center;
            color: #718096;
            font-size: 0.85rem;
        }
    </style>
</head>
<body>

    <div class="container header-section">
        <div class="brand-badge">🇸🇦 منصة سلنقح التفاعلية المباشرة 🇸🇦</div>
        <h1 class="hero-title">التحميل والتعديل الذكي المباشر من الموقع</h1>
    </div>

    <div class="container col-lg-8">
        <ul class="nav nav-pills justify-content-center mb-4" id="pills-tab" role="tablist">
            <li class="nav-item">
                <button class="nav-link active" id="tab-download" data-bs-toggle="pill" data-bs-target="#content-download">📥 تحميل مقطع</button>
            </li>
            <li class="nav-item">
                <button class="nav-link" id="tab-enhance" data-bs-toggle="pill" data-bs-target="#content-enhance">⚡ توضيح فيديو</button>
            </li>
            <li class="nav-item">
                <button class="nav-link" id="tab-card" data-bs-toggle="pill" data-bs-target="#content-card">🎨 بطاقة تهنئة</button>
            </li>
        </ul>

        <div class="tab-content" id="pills-tabContent">
            <div class="tab-pane fade show active" id="content-download">
                <div class="tool-card">
                    <h4 class="fw-bold text-center mb-3">📥 تنزيل مقطع من رابط</h4>
                    <p class="text-center text-secondary mb-4">ضع رابط الفيديوهات (تيك توك، انستقرام، يوتيوب) لتحميله مباشرة لجوالك.</p>
                    <div class="input-group mb-3">
                        <input type="url" id="dl-url" class="form-control" placeholder="أدخل رابط الفيديو هنا..." required>
                        <button class="btn btn-green" id="btn-dl" onclick="processDownload()">تحميل الان</button>
                    </div>
                    <div id="dl-status" class="mt-3 text-center"></div>
                </div>
            </div>

            <div class="tab-pane fade" id="content-enhance">
                <div class="tool-card">
                    <h4 class="fw-bold text-center mb-3">⚡ توضيح ورفع دقة الفيديو</h4>
                    <p class="text-center text-secondary mb-4">اختر فيديو من جوالك وسيقوم الموقع بتوضيح معالمه وتحسين حدة الألوان مباشرة.</p>
                    <div class="mb-3">
                        <input class="form-control" type="file" id="enhance-file" accept="video/*">
                    </div>
                    <div class="text-center">
                        <button class="btn btn-green w-100" id="btn-enhance" onclick="processEnhance()">توضيح المقطع الآن</button>
                    </div>
                    <div id="enhance-status" class="mt-4 text-center"></div>
                </div>
            </div>

            <div class="tab-pane fade" id="content-card">
                <div class="tool-card">
                    <h4 class="fw-bold text-center mb-3">🎨 تصميم بطاقة تهنئة فورية</h4>
                    <p class="text-center text-secondary mb-4">اكتب الاسم أو العبارة لتصميم بطاقتك الخاصة باليوم الوطني 96.</p>
                    <div class="mb-3">
                        <input type="text" id="card-text" class="form-control" placeholder="مثال: كل عام والوطن بخير - سلمان">
                    </div>
                    <div class="text-center">
                        <button class="btn btn-green w-100" id="btn-card" onclick="processCard()">إنشاء البطاقة</button>
                    </div>
                    <div id="card-status" class="mt-4 text-center"></div>
                </div>
            </div>
        </div>

        <div class="text-center my-3">
            <a href="https://t.me/{{ bot_username if bot_username else '' }}" target="_blank" class="text-decoration-none text-success">
                🟢 تفضل استخدام تيليجرام؟ اضغط هنا للذهاب للبوت
            </a>
        </div>
    </div>

    <footer>
        <div class="container">
            <p class="mb-0">حقوق البرمجة والتطوير محفوظة لمطور الخدمة © 2026 | منصة سلنقح</p>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        async function processDownload() {
            const url = document.getElementById('dl-url').value;
            const status = document.getElementById('dl-status');
            const btn = document.getElementById('btn-dl');
            if (!url) { alert('يرجى إدخال الرابط أولاً'); return; }
            btn.disabled = true;
            status.innerHTML = '<div class="spinner-border text-success"></div> <p class="mt-2 text-warning">جاري معالجة واستخراج المقطع...</p>';
            try {
                const res = await fetch('/api/web_download', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: url})
                });
                const data = await res.json();
                if (data.success) {
                    status.innerHTML = `<a href="${data.url}" class="btn btn-success" download>✅ اضغط هنا لتنزيل الفيديو</a>`;
                } else {
                    status.innerHTML = `<span class="text-danger">❌ ${data.error}</span>`;
                }
            } catch(e) {
                status.innerHTML = '<span class="text-danger">❌ حدث خطأ أثناء الاتصال بالسيرفر.</span>';
            }
            btn.disabled = false;
        }

        async function processEnhance() {
            const fileInput = document.getElementById('enhance-file');
            const status = document.getElementById('enhance-status');
            const btn = document.getElementById('btn-enhance');
            if (!fileInput.files[0]) { alert('يرجى اختيار فيديو من جهازك'); return; }
            const formData = new FormData();
            formData.append('video', fileInput.files[0]);
            btn.disabled = true;
            status.innerHTML = '<div class="spinner-border text-success"></div> <p class="mt-2 text-warning">جاري رفع وتوضيح الفيديو مجاناً عبر السيرفر...</p>';
            try {
                const res = await fetch('/api/web_enhance', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.success) {
                    status.innerHTML = `
                        <p class="text-success fw-bold">✅ تم توضيح المقطع بنجاح!</p>
                        <video controls style="max-width:100%; border-radius:12px; margin-bottom:10px;">
                            <source src="${data.url}" type="video/mp4">
                        </video><br>
                        <a href="${data.url}" class="btn btn-success" download>📥 تحميل الفيديو الموضح</a>
                    `;
                } else {
                    status.innerHTML = `<span class="text-danger">❌ ${data.error}</span>`;
                }
            } catch(e) {
                status.innerHTML = '<span class="text-danger">❌ تعذر معالجة الفيديو.</span>';
            }
            btn.disabled = false;
        }

        async function processCard() {
            const text = document.getElementById('card-text').value;
            const status = document.getElementById('card-status');
            const btn = document.getElementById('btn-card');
            btn.disabled = true;
            status.innerHTML = '<div class="spinner-border text-success"></div> <p class="mt-2 text-warning">جاري تصميم البطاقة...</p>';
            try {
                const res = await fetch('/api/web_card', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text: text})
                });
                const data = await res.json();
                if (data.success) {
                    status.innerHTML = `
                        <img src="${data.image}" style="max-width:100%; border-radius:12px; margin-bottom:10px;"><br>
                        <a href="${data.image}" class="btn btn-success" download="card.png">📥 تنزيل البطاقة</a>
                    `;
                } else {
                    status.innerHTML = `<span class="text-danger">❌ ${data.error}</span>`;
                }
            } catch(e) {
                status.innerHTML = '<span class="text-danger">❌ فشل في إنشاء البطاقة.</span>';
            }
            btn.disabled = false;
        }
    </script>
</body>
</html>
"""

# ==========================================
# 2. مسارات API لخدمات الويب المباشرة
# ==========================================
@app.route('/')
def home():
    bot_name = os.getenv("BOT_USERNAME", "")
    return render_template_string(HTML_TEMPLATE, bot_username=bot_name)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/api/web_download', methods=['POST'])
def web_download():
    data = request.json or {}
    url = data.get('url')
    if not url: return jsonify({'success': False, 'error': 'الرابط غير متاح'})
    try:
        timestamp = int(time.time())
        out_name = f"web_dl_{timestamp}.mp4"
        out_path = os.path.join(UPLOAD_FOLDER, out_name)
        ydl_opts = {'format': 'best', 'outtmpl': out_path, 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        increment_stats()
        return jsonify({'success': True, 'url': f'/uploads/{out_name}'})
    except Exception as e:
        logger.error(f"Web DL Error: {e}")
        return jsonify({'success': False, 'error': 'تعذر استخراج الفيديو من هذا الرابط.'})

@app.route('/api/web_enhance', methods=['POST'])
def web_enhance():
    if 'video' not in request.files:
        return jsonify({'success': False, 'error': 'لم يتم العثور على ملف الفيديو'})
    file = request.files['video']
    timestamp = int(time.time())
    in_name = f"web_in_{timestamp}.mp4"
    out_name = f"web_out_{timestamp}.mp4"
    in_path = os.path.join(UPLOAD_FOLDER, in_name)
    out_path = os.path.join(UPLOAD_FOLDER, out_name)
    file.save(in_path)

    try:
        filter_str = "scale=w='trunc(iw*1.3/2)*2':h='trunc(ih*1.3/2)*2':flags=bicubic,unsharp=3:3:1.0:3:3:0.0,eq=contrast=1.05:saturation=1.1"
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", in_path,
            "-vf", filter_str, "-c:v", "libx264",
            "-preset", "ultrafast", "-crf", "23",
            "-threads", "0", "-c:a", "aac", "-b:a", "128k",
            out_path
        ]
        process = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode == 0 and os.path.exists(out_path):
            increment_stats()
            if os.path.exists(in_path): os.remove(in_path)
            return jsonify({'success': True, 'url': f'/uploads/{out_name}'})
        else:
            return jsonify({'success': False, 'error': 'فشلت معالجة الفيديو.'})
    except Exception as e:
        logger.error(f"Web Enhance Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/web_card', methods=['POST'])
def web_card():
    data = request.json or {}
    text_val = data.get('text') or "دام عزك يا وطن 🇸🇦"
    bio = create_card_image(text_val)
    if bio:
        base64_img = base64.b64encode(bio.getvalue()).decode('utf-8')
        return jsonify({'success': True, 'image': f'data:image/png;base64,{base64_img}'})
    return jsonify({'success': False, 'error': 'فشل إنشاء البطاقة'})

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# 3. البيانات والإحصائيات
# ==========================================
COUNTER_FILE = "stats.json"
USERS_FILE = "users.json"
REFERRALS_FILE = "referrals.json"

ADMIN_ID = os.getenv("ADMIN_ID")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
WEB_SITE_URL = os.getenv("WEB_SITE_URL", "https://ab-rbx9.onrender.com").rstrip('/')

def get_stats():
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, 'r') as f: return json.load(f)
        except: pass
    return {"downloads": 0}

def increment_stats():
    stats = get_stats()
    stats["downloads"] = stats.get("downloads", 0) + 1
    with open(COUNTER_FILE, 'w') as f: json.dump(stats, f)
    return stats["downloads"]

def save_user(user_id):
    users = set()
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f: users = set(json.load(f))
        except: pass
    users.add(user_id)
    with open(USERS_FILE, 'w') as f: json.dump(list(users), f)

def get_referrals():
    if os.path.exists(REFERRALS_FILE):
        try:
            with open(REFERRALS_FILE, 'r') as f: return json.load(f)
        except: pass
    return {}

def get_user_ref_count(user_id):
    return len(get_referrals().get(str(user_id), []))

def save_referral(referrer_id, referred_id):
    refs = get_referrals()
    key = str(referrer_id)
    if key not in refs: refs[key] = []
    if referred_id not in refs[key]:
        refs[key].append(referred_id)
        with open(REFERRALS_FILE, 'w') as f: json.dump(refs, f)

# ==========================================
# 4. واجهة تيليجرام
# ==========================================
WELCOME_TEXT = (
    "🇸🇦 **كل عام والوطن بألف خير | اليوم الوطني السعودي 96** 🇸🇦\n\n"
    "أهلاً بك في بوت سلنقح للتحميل والتوضيح السريع المجاني! ⚡\n\n"
    "• **لتحميل فيديو من التواصل:** أرسل رابط المقطع مباشرة.\n"
    "• **لتوضيح ورفع دقة فيديو بجوالك:** أرسل ملف الفيديو هنا فوراً وسيقوم البوت بمعالجته بشكل سريع ومجاني! 🎬\n\n"
    "🛡 حقوق البرمجة والتطوير محفوظة لمطور الخدمة ©"
)

def get_main_keyboard(user_id):
    ref_count = get_user_ref_count(user_id)
    keyboard = [
        [InlineKeyboardButton("🚀 زيارة موقع الخدمة التفاعلي", url=WEB_SITE_URL)],
        [InlineKeyboardButton("🎨 إنشاء بطاقة تهنئة باليوم الوطني", callback_data="cmd_card")],
        [InlineKeyboardButton(f"🎁 رابط الدعوة الخاص بك ({ref_count} مدعوين)", callback_data="cmd_ref")],
        [InlineKeyboardButton("📜 شروط الاستخدام وإخلاء المسؤولية", callback_data="cmd_terms")],
        [InlineKeyboardButton("🟢 مشاركة البوت مع الأصدقاء", switch_inline_query="🚀 جرب بوت سلنقح للتحميل وتوضيح المقاطع مجاناً!")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    if context.args:
        referrer_id = context.args[0]
        if referrer_id != str(user_id): save_referral(referrer_id, user_id)
    await update.message.reply_text(WELCOME_TEXT, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

async def main_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    bot_username = context.bot.username or "bot"
    await query.answer()

    if data == "cmd_main":
        await query.edit_message_text(WELCOME_TEXT, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
    elif data == "cmd_card":
        text = "🎨 **إنشاء بطاقة تهنئة:**\n\nاكتب `/card` متبوعاً بنصك."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="cmd_main")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    elif data == "cmd_ref":
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        text = f"🎁 **رابط الدعوة:**\n`{ref_link}`\n\n📊 **عدد المدعوين:** `{get_user_ref_count(user_id)}`"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="cmd_main")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    elif data == "cmd_terms":
        text = "📜 **شروط الاستخدام:**\nهذا البوت والخدمة مجانية 100% للاستخدام الشخصي."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="cmd_main")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

async def handle_video_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    status_msg = await update.message.reply_text("⚡ **جاري تنزيل الفيديو وتوضيحه بسرعة...**")

    input_path = None
    output_path = None

    try:
        video_obj = update.message.video or update.message.document
        if hasattr(video_obj, 'file_size') and video_obj.file_size > 20 * 1024 * 1024:
            await status_msg.edit_text("⚠️ **حجم الفيديو يتجاوز 20 ميجابايت.**")
            return

        video_file = await context.bot.get_file(video_obj.file_id)
        timestamp = int(time.time())
        input_path = os.path.join(UPLOAD_FOLDER, f"in_{user_id}_{timestamp}.mp4")
        output_path = os.path.join(UPLOAD_FOLDER, f"out_{user_id}_{timestamp}.mp4")

        await video_file.download_to_drive(input_path)

        filter_str = "scale=w='trunc(iw*1.3/2)*2':h='trunc(ih*1.3/2)*2':flags=bicubic,unsharp=3:3:1.0:3:3:0.0,eq=contrast=1.05:saturation=1.1"
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", filter_str, "-c:v", "libx264",
            "-preset", "ultrafast", "-crf", "23",
            "-threads", "0", "-c:a", "aac", "-b:a", "128k",
            output_path
        ]
        process = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if process.returncode == 0 and os.path.exists(output_path):
            increment_stats()
            await status_msg.edit_text("✅ **تمت المعالجة والتوضيح بنجاح!**")
            with open(output_path, 'rb') as video_out:
                await update.message.reply_video(video=video_out, caption="⚡ **تم توضيح المقطع بنجاح!**")
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ متعذر معالجة هذا الفيديو.")
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        await status_msg.edit_text(f"❌ **حدث خطأ:** `{str(e)}`", parse_mode="Markdown")
    finally:
        for p in [input_path, output_path]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass

def create_card_image(text_content):
    if not HAS_PIL: return None
    img = Image.new('RGB', (800, 400), color=(15, 81, 50))
    d = ImageDraw.Draw(img)
    d.text((50, 180), f"{text_content}", fill=(255, 255, 255))
    bio = BytesIO()
    bio.name = 'card.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

async def card_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = " ".join(context.args) if context.args else "دام عزك يا وطن 🇸🇦"
    msg = await update.message.reply_text("🎨 جاري تصميم البطاقة...")
    bio = create_card_image(user_text)
    if bio:
        await update.message.reply_photo(photo=bio, caption=f"🖼 **بطاقتك جاهزة:**\n{user_text}")
        await msg.delete()
    else:
        await msg.edit_text(f"🖼 **بطاقتك:**\n{user_text}")

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = [
        InlineQueryResultArticle(
            id="1",
            title="مشاركة بوت اليوم الوطني والتحميل",
            input_message_content=InputTextMessageContent("🇸🇦 جرب بوت سلنقح للتحميل وتوضيح الفيديوهات مجاناً!")
        )
    ]
    await update.inline_query.answer(results)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    if update.effective_user: save_user(update.effective_user.id)

    if text.startswith("http://") or text.startswith("https://"):
        msg = await update.message.reply_text("⏳ جاري معالجة الرابط والتحميل...")
        try:
            ydl_opts = {'format': 'best', 'outtmpl': 'downloaded_video.%(ext)s', 'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                filename = ydl.prepare_filename(info)

            increment_stats()
            with open(filename, 'rb') as video_file:
                await update.message.reply_video(video=video_file, caption="✅ تم التحميل بنجاح!")
            if os.path.exists(filename): os.remove(filename)
            await msg.delete()
        except Exception as e:
            logger.error(f"Error downloading: {e}")
            await msg.edit_text("❌ حدث خطأ أثناء تنزيل المقطع.")
    else:
        await start(update, context)

# ==========================================
# 5. تشغيل البوت مع التغيير التلقائي للجلسات المعلقة
# ==========================================
def main():
    keep_alive()

    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

    bot_app = Application.builder().token(TOKEN).build()

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("card", card_command))
    bot_app.add_handler(CallbackQueryHandler(main_callback_handler))
    bot_app.add_handler(InlineQueryHandler(inline_query_handler))
    bot_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video_upload))
    bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🤖 البوت يعمل ومستعد لاستقبال الأوامر...")
    # إضافة drop_pending_updates=True لمسح أي جلسات أو تعارضات قديمة تلقائياً
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
