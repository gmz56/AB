import os
import json
import time
import random
import string
import logging
import subprocess
import yt_dlp
import asyncio
from threading import Thread
from flask import Flask, send_from_directory, render_template_string, request, jsonify

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# إعداد التسجيل (Logging)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# مجلدات الملفات
UPLOAD_FOLDER = 'temp_uploads'
RECEIPTS_FOLDER = 'receipts_uploads'
for folder in [UPLOAD_FOLDER, RECEIPTS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

DATA_FILE = "database.json"
COUNTER_FILE = "stats.json"

# جلب متغيرات البيئة من Render
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEB_SITE_URL = os.getenv("WEB_SITE_URL", "https://ab-rbx9.onrender.com").rstrip('/')
STC_PAY_NUM = os.getenv("STC_PAY_NUMBER", "لم يحدد")
IBAN_NUM = os.getenv("IBAN_NUMBER", "لم يحدد")
BOT_NAME = os.getenv("BOT_USERNAME", "")

# --- إدارة قاعدة البيانات ---
def load_db():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: pass
    return {"users": [], "vips": [], "codes": []}

def save_db(db):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

def is_vip(user_id):
    db = load_db()
    return (user_id in db.get("vips", [])) or (user_id == ADMIN_ID)

def increment_stats():
    stats = {"downloads": 0}
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, 'r') as f: stats = json.load(f)
        except Exception: pass
    stats["downloads"] = stats.get("downloads", 0) + 1
    with open(COUNTER_FILE, 'w') as f: json.dump(stats, f)
    return stats["downloads"]

# ==========================================
# 1. واجهة الموقع التفاعلي (Flask HTML)
# ==========================================
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>منصة VIP | التحميل والتوضيح 🇸🇦</title>
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
        .header-section { padding: 30px 20px 10px; text-align: center; }
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
            background: linear-gradient(45deg, #f1c40f, #2ecc71, #ffffff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .tool-card {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 25px;
            backdrop-filter: blur(10px);
            margin-bottom: 30px;
        }
        .nav-pills .nav-link {
            color: #a0aec0;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            margin: 0 4px;
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
            border-color: #f1c40f;
            box-shadow: 0 0 10px rgba(241, 196, 15, 0.3);
        }
        .btn-green {
            background: #198754; color: white; font-weight: 700;
            padding: 12px 28px; border-radius: 12px; border: none;
        }
        .btn-green:hover { background: #146c43; color: white; }
        .price-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(241, 196, 15, 0.3);
            border-radius: 15px;
            padding: 15px;
            text-align: center;
            transition: 0.3s;
        }
        .price-card:hover { border-color: #f1c40f; transform: translateY(-3px); }
        .price-title { font-size: 1.1rem; font-weight: 800; color: #f1c40f; }
        .price-val { font-size: 1.5rem; font-weight: 900; color: #fff; margin: 5px 0; }
        .feature-item { font-size: 0.9rem; margin-bottom: 6px; }
        footer { margin-top: auto; border-top: 1px solid rgba(255, 255, 255, 0.08); padding: 20px 0; text-align: center; color: #718096; }
    </style>
</head>
<body>

    <div class="container header-section">
        <div class="brand-badge">👑 الباقة الملكية - VIP Access</div>
        <h1 class="hero-title">منصة التحميل والاشتراك الفوري</h1>
    </div>

    <div class="container col-lg-8">
        <ul class="nav nav-pills justify-content-center mb-4" id="pills-tab">
            <li class="nav-item">
                <button class="nav-link active" id="tab-download" data-bs-toggle="pill" data-bs-target="#content-download">📥 تحميل مقطع</button>
            </li>
            <li class="nav-item">
                <button class="nav-link" id="tab-enhance" data-bs-toggle="pill" data-bs-target="#content-enhance">⚡ توضيح فيديو</button>
            </li>
            <li class="nav-item">
                <button class="nav-link text-warning fw-bold" id="tab-vip" data-bs-toggle="pill" data-bs-target="#content-vip">⭐ باقات VIP والدفع</button>
            </li>
        </ul>

        <div class="tab-content">
            <!-- التحميل المجاني -->
            <div class="tab-pane fade show active" id="content-download">
                <div class="tool-card">
                    <h4 class="fw-bold text-center mb-3">📥 تنزيل مقطع من الرابط</h4>
                    <div class="input-group mb-3">
                        <input type="url" id="dl-url" class="form-control" placeholder="أدخل رابط المقطع هنا...">
                        <button class="btn btn-green" id="btn-dl" onclick="processDownload()">تحميل الآن</button>
                    </div>
                    <div id="dl-status" class="mt-3 text-center"></div>
                </div>
            </div>

            <!-- التوضيح -->
            <div class="tab-pane fade" id="content-enhance">
                <div class="tool-card">
                    <h4 class="fw-bold text-center mb-3">⚡ توضيح ورفع دقة الفيديو</h4>
                    <div class="mb-3">
                        <input class="form-control" type="file" id="enhance-file" accept="video/*">
                    </div>
                    <button class="btn btn-green w-100" id="btn-enhance" onclick="processEnhance()">توضيح المقطع الآن</button>
                    <div id="enhance-status" class="mt-4 text-center"></div>
                </div>
            </div>

            <!-- قسم VIP والأسعار ودفع الإيصالات -->
            <div class="tab-pane fade" id="content-vip">
                <div class="tool-card">
                    <h4 class="fw-bold text-center text-warning mb-3">⭐ مميزات باقات اشتراك VIP</h4>
                    
                    <!-- عرض أسعار الاشتراكات -->
                    <div class="row g-3 mb-4">
                        <div class="col-md-4">
                            <div class="price-card">
                                <div class="price-title">باقة اليوم</div>
                                <div class="price-val">10 ريال</div>
                                <div class="text-muted fs-7">تجربة سريعة لمدة 24 ساعة</div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="price-card border-warning">
                                <div class="price-title">الباقة الشهريّة 🔥</div>
                                <div class="price-val text-warning">25 ريال</div>
                                <div class="text-muted fs-7">تفعيل كامل لمدة 30 يوم</div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="price-card">
                                <div class="price-title">باقة مدى الحياة</div>
                                <div class="price-val">99 ريال</div>
                                <div class="text-muted fs-7">تفعيل دائم بلا حدود</div>
                            </div>
                        </div>
                    </div>

                    <!-- قائمة الـ 12 ميزة -->
                    <div class="p-3 mb-4" style="background: rgba(0,0,0,0.3); border-radius:15px;">
                        <h6 class="text-warning fw-bold mb-3">💎 تتضمن حزمة الـ VIP الميزات الـ 12 التالية:</h6>
                        <div class="row">
                            <div class="col-6 feature-item">1. 🚀 رفع الحجم إلى 100MB</div>
                            <div class="col-6 feature-item">2. 🎬 إزالة حقوق المنصات</div>
                            <div class="col-6 feature-item">3. ✨ جودة Ultra-HD و 60FPS</div>
                            <div class="col-6 feature-item">4. 🎵 استخراج الصوت MP3</div>
                            <div class="col-6 feature-item">5. 📝 ترجمة وكتابة تلقائية</div>
                            <div class="col-6 feature-item">6. 🎙️ تعليق صوتي بالذكاء الاصطناعي</div>
                            <div class="col-6 feature-item">7. 🖼️ إضافة لوجو خاص بك</div>
                            <div class="col-6 feature-item">8. ⚡ أولوية سرعة المعالجة</div>
                            <div class="col-6 feature-item">9. 📦 تحميل متعدد دفعة واحدة</div>
                            <div class="col-6 feature-item">10. 🏷️ إزالة اسم حقوق البوت</div>
                            <div class="col-6 feature-item">11. 🎴 بطاقات وتصاميم حصرية</div>
                            <div class="col-6 feature-item">12. 👑 خدمة دعم فني مباشر</div>
                        </div>
                    </div>

                    <!-- بيانات التحويل المباشر -->
                    <div class="p-3 mb-4 border border-warning rounded-3" style="background: rgba(241, 196, 15, 0.05);">
                        <h6 class="fw-bold text-warning mb-2">💳 طرق التحويل والدفع المباشر:</h6>
                        <p class="mb-1">📲 <b>STC Pay:</b> <code class="fs-6 text-white">{{ stc_pay }}</code></p>
                        <p class="mb-0">🏦 <b>الآيبان البنكي:</b> <code class="fs-6 text-white">{{ iban }}</code></p>
                    </div>

                    <!-- نموذج رفع الإيصال -->
                    <form id="vip-form" onsubmit="submitReceipt(event)">
                        <div class="mb-3">
                            <label class="form-label">معرف حسابك في تيليجرام (User ID أو اليوزر):</label>
                            <input type="text" id="vip-user-id" class="form-control" placeholder="مثال: @username أو 5310636822" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">صورة إيصال التحويل:</label>
                            <input type="file" id="vip-receipt" class="form-control" accept="image/*" required>
                        </div>
                        <button type="submit" class="btn btn-warning w-100 fw-bold fs-6 py-2" id="btn-vip-sub">📤 إرسال الإيصال للتفعيل الفوري</button>
                    </form>
                    <div id="vip-status" class="mt-3 text-center"></div>
                </div>
            </div>
        </div>

        <div class="text-center my-3">
            <a href="https://t.me/{{ bot_username if bot_username else '' }}" target="_blank" class="text-decoration-none text-success fw-bold">
                🟢 فتح البوت مباشرة في تطبيق تيليجرام
            </a>
        </div>
    </div>

    <footer>
        <p class="mb-0">جميع الحقوق محفوظة © 2026 | تطوير منصة VIP</p>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        async function processDownload() {
            const url = document.getElementById('dl-url').value;
            const status = document.getElementById('dl-status');
            if (!url) { alert('يرجى إدخال الرابط'); return; }
            status.innerHTML = '<div class="spinner-border text-success"></div> <p class="mt-2 text-warning">جاري التنزيل والمعالجة...</p>';
            try {
                const res = await fetch('/api/web_download', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: url})
                });
                const data = await res.json();
                if (data.success) {
                    status.innerHTML = `<a href="${data.url}" class="btn btn-success" download>✅ تنزيل الفيديو الموضح</a>`;
                } else {
                    status.innerHTML = `<span class="text-danger">❌ ${data.error}</span>`;
                }
            } catch(e) { status.innerHTML = '<span class="text-danger">❌ حدث خطأ أثناء التنزيل.</span>'; }
        }

        async function processEnhance() {
            const fileInput = document.getElementById('enhance-file');
            const status = document.getElementById('enhance-status');
            if (!fileInput.files[0]) { alert('اختر ملف فيديو'); return; }
            const formData = new FormData();
            formData.append('video', fileInput.files[0]);
            status.innerHTML = '<div class="spinner-border text-success"></div> <p class="mt-2 text-warning">جاري توضيح الفيديو...</p>';
            try {
                const res = await fetch('/api/web_enhance', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.success) {
                    status.innerHTML = `<video controls style="max-width:100%; border-radius:12px;" class="mb-2"><source src="${data.url}"></video><br><a href="${data.url}" class="btn btn-success" download>📥 تحميل الموضح</a>`;
                } else { status.innerHTML = `<span class="text-danger">❌ ${data.error}</span>`; }
            } catch(e) { status.innerHTML = '<span class="text-danger">❌ تعذر التوضيح.</span>'; }
        }

        async function submitReceipt(e) {
            e.preventDefault();
            const userId = document.getElementById('vip-user-id').value;
            const fileInput = document.getElementById('vip-receipt');
            const status = document.getElementById('vip-status');
            const btn = document.getElementById('btn-vip-sub');

            if (!fileInput.files[0]) { alert('اختر صورة الإيصال'); return; }

            const formData = new FormData();
            formData.append('user_info', userId);
            formData.append('receipt', fileInput.files[0]);

            btn.disabled = true;
            status.innerHTML = '<div class="spinner-border text-warning"></div> <p class="mt-2 text-warning">جاري إرسال الإيصال للأدمن للتحقق...</p>';

            try {
                const res = await fetch('/api/web_pay_receipt', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.success) {
                    status.innerHTML = '<div class="alert alert-success">✅ تم إرسال إيصالك بنجاح! سيتم التحقق وتفعيل حسابك في تيليجرام فوراً.</div>';
                } else {
                    status.innerHTML = `<div class="alert alert-danger">❌ ${data.error}</div>`;
                }
            } catch(e) {
                status.innerHTML = '<div class="alert alert-danger">❌ حدث خطأ أثناء إرسال الإيصال.</div>';
            }
            btn.disabled = false;
        }
    </script>
</body>
</html>
"""

# ==========================================
# 2. مسارات ومعالجات Flask
# ==========================================
telegram_app_instance = None

@app.route('/')
def home():
    return render_template_string(
        HTML_TEMPLATE,
        bot_username=BOT_NAME,
        stc_pay=STC_PAY_NUM,
        iban=IBAN_NUM
    )

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/api/web_download', methods=['POST'])
def web_download():
    data = request.json or {}
    url = data.get('url')
    if not url: return jsonify({'success': False, 'error': 'الرابط مفقود'})
    try:
        timestamp = int(time.time())
        out_name = f"web_dl_{timestamp}.mp4"
        out_path = os.path.join(UPLOAD_FOLDER, out_name)
        ydl_opts = {'format': 'best', 'outtmpl': out_path, 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
        increment_stats()
        return jsonify({'success': True, 'url': f'/uploads/{out_name}'})
    except Exception:
        return jsonify({'success': False, 'error': 'فشل تنزيل المقطع من الرابط.'})

@app.route('/api/web_enhance', methods=['POST'])
def web_enhance():
    if 'video' not in request.files: return jsonify({'success': False, 'error': 'لم يتم اختيار فيديو'})
    file = request.files['video']
    timestamp = int(time.time())
    in_path = os.path.join(UPLOAD_FOLDER, f"in_{timestamp}.mp4")
    out_path = os.path.join(UPLOAD_FOLDER, f"out_{timestamp}.mp4")
    file.save(in_path)
    try:
        filter_str = "scale=w='trunc(iw*1.3/2)*2':h='trunc(ih*1.3/2)*2':flags=bicubic,unsharp=3:3:1.0:3:3:0.0,eq=contrast=1.05:saturation=1.1"
        cmd = ["ffmpeg", "-y", "-i", in_path, "-vf", filter_str, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-c:a", "aac", out_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if os.path.exists(out_path):
            increment_stats()
            if os.path.exists(in_path): os.remove(in_path)
            return jsonify({'success': True, 'url': f'/uploads/out_{timestamp}.mp4'})
    except Exception: pass
    return jsonify({'success': False, 'error': 'فشلت معالجة الفيديو.'})

@app.route('/api/web_pay_receipt', methods=['POST'])
def web_pay_receipt():
    user_info = request.form.get('user_info', '')
    if 'receipt' not in request.files or not user_info:
        return jsonify({'success': False, 'error': 'يرجى كتابة المعرف وإرفاق صورة الإيصال'})
    
    file = request.files['receipt']
    timestamp = int(time.time())
    receipt_filename = f"receipt_{timestamp}.png"
    receipt_path = os.path.join(RECEIPTS_FOLDER, receipt_filename)
    file.save(receipt_path)

    # إرسال صورة الإيصال إلى حساب الأدمن في تيليجرام مع زرين
    if telegram_app_instance and ADMIN_ID:
        try:
            keyboard = [
                [
                    InlineKeyboardButton("🟢 موافقة وتفعيل VIP", callback_data=f"approve_vip_{user_info}"),
                    InlineKeyboardButton("🔴 رفض الطلب", callback_data=f"reject_vip_{user_info}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            caption = f"💳 **وصل إيصال تحويل جديد من الموقع!**\n\n👤 **معرف العميل:** `{user_info}`\n🕒 **التاريخ:** {time.strftime('%Y-%m-%d %H:%M')}"
            
            asyncio.run_coroutine_threadsafe(
                telegram_app_instance.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=open(receipt_path, 'rb'),
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                ),
                telegram_app_instance.loop
            )
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error sending receipt: {e}")
            return jsonify({'success': False, 'error': 'تعذر إرسال الإيصال للأدمن حالياً.'})
            
    return jsonify({'success': False, 'error': 'السيرفر غير متصل بالبوت.'})

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 3. أحداث وأوامر بوت تيليجرام
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = load_db()
    if user_id not in db.get("users", []):
        db.setdefault("users", []).append(user_id)
        save_db(db)

    vip_str = "🌟 مشترك VIP" if is_vip(user_id) else "👤 حساب مجاني"
    text = (
        f"🇸🇦 **أهلاً بك في بوت الخدمة الشاملة للتحميل والتوضيح**\n\n"
        f"حالة حسابك: **{vip_str}**\n\n"
        f"• أرسل رابط أي مقطع لتنزيله.\n"
        f"• أرسل فيديو لتوضيحه وتنعيمه تلقائياً.\n"
        f"• لتفعيل الاشتراك عبر كود استخدم: `/redeem الكود`"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ الـ 12 ميزة والباقات (VIP)", callback_data="cmd_vip_info")],
        [InlineKeyboardButton("🚀 فتح موقع التحميل والدفع", url=WEB_SITE_URL)]
    ])
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

async def vip_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    vip_str = "🌟 أنت مشترك بالفعل كـ VIP!" if is_vip(user_id) else "👤 حسابك حالياً مجاني."
    
    vip_text = (
        f"👑 **باقات واشتراكات الـ VIP ({vip_str}):**\n\n"
        f"💰 **الأسعار:**\n"
        f"• باقة اليوم: **10 ريال**\n"
        f"• الباقة الشهرية: **25 ريال**\n"
        f"• باقة مدى الحياة: **99 ريال**\n\n"
        f"💎 **حزمة الـ 12 ميزة كاملة:**\n"
        f"1. معالجة ملفات ضخمة تصل إلى 100MB\n"
        f"2. تنزيل بدون حقوق المنصات (تيك توك/انستقرام)\n"
        f"3. توضيح وتنعيم فائقة Ultra-HD 60FPS\n"
        f"4. استخراج الصوت MP3 بضغطة زر\n"
        f"5. ترجمة وكتابة نصوص تلقائية على المقطع\n"
        f"6. تعليق صوتي واقعي بالذكاء الاصطناعي\n"
        f"7. دمج شعارك/اللوجو الخاص بك تلقائياً\n"
        f"8. أولوية معالجة فائقة السرعة بدون طابور\n"
        f"9. تحميل روابط متعددة دفعة واحدة\n"
        f"10. إزالة حقوق واسم البوت عن كافة الملفات\n"
        f"11. تصاميم وإطارات حصرية لمشتركي VIP\n"
        f"12. دعم فني وأولوية معالجة دائمين\n\n"
        f"💳 **للدفع والتفعيل:** افتح رابط الموقع بالأسفل واضغط على تبويب 'باقات VIP والدفع' لرفع صورة الإيصال."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 الانتقال للموقع والدفع", url=WEB_SITE_URL)]
    ])
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(vip_text, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.message.reply_text(vip_text, reply_markup=kb, parse_mode="Markdown")

async def admin_make_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    code = "VIP-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    db = load_db()
    db.setdefault("codes", []).append(code)
    save_db(db)
    await update.message.reply_text(f"🎟️ **كود VIP جديد:**\n`{code}`", parse_mode="Markdown")

async def user_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("⚠️ اكتب الأمر متبوعاً بالكود، مثال:\n`/redeem VIP-XXXXXX`", parse_mode="Markdown")
        return
    code = context.args[0].strip()
    db = load_db()
    if code in db.get("codes", []):
        db["codes"].remove(code)
        if user_id not in db.get("vips", []):
            db.setdefault("vips", []).append(user_id)
        save_db(db)
        await update.message.reply_text("🎉 **تم تفعيل اشتراك VIP بحسابك بنجاح!** استمتع بالـ 12 ميزة الحصرية الآن.")
    else:
        await update.message.reply_text("❌ الكود غير صحيح أو تم استخدامه سابقاً.")

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data.startswith("approve_vip_"):
        user_info = data.replace("approve_vip_", "")
        db = load_db()
        
        try:
            target_id = int(user_info)
            if target_id not in db.get("vips", []):
                db.setdefault("vips", []).append(target_id)
                save_db(db)
            
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text="🎉 **تم اعتماد إيصال التحويل وتفعيل اشتراك VIP بحسابك بنجاح!**"
                )
            except Exception: pass
        except ValueError:
            pass

        await query.edit_message_caption(caption=query.message.caption + "\n\n🟢 **تمت الموافقة وتفعيل الـ VIP للعميل بنجاح!**")

    elif data.startswith("reject_vip_"):
        await query.edit_message_caption(caption=query.message.caption + "\n\n🔴 **تم رفض الطلب.**")

    elif data == "cmd_vip_info":
        await vip_info_command(update, context)

async def handle_media_or_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    
    if text.startswith("http"):
        msg = await update.message.reply_text("⚡ جاري تنزيل المقطع...")
        try:
            ydl_opts = {'format': 'best', 'outtmpl': 'dl_vid.mp4', 'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                fn = ydl.prepare_filename(info)
            increment_stats()
            with open(fn, 'rb') as vf:
                await update.message.reply_video(video=vf, caption="✅ تم التحميل بنجاح!")
            if os.path.exists(fn): os.remove(fn)
            await msg.delete()
        except Exception:
            await msg.edit_text("❌ تعذر تنزيل هذا الرابط.")
    else:
        await start(update, context)

# ==========================================
# 4. بداية التشغيل الرئيسي
# ==========================================
def main():
    global telegram_app_instance
    
    # تشغيل Flask في الخلفية
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

    if not TOKEN: raise ValueError("TELEGRAM_BOT_TOKEN غير مسجل!")

    bot_app = Application.builder().token(TOKEN).build()
    telegram_app_instance = bot_app

    # تسجيل الأوامر والروابط
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("vip", vip_info_command))
    bot_app.add_handler(CommandHandler("makecode", admin_make_code))
    bot_app.add_handler(CommandHandler("redeem", user_redeem))
    bot_app.add_handler(CallbackQueryHandler(admin_callback_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_media_or_text))

    print("🤖 السيرفر والموقع والبوت يعملون بنجاح...")
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
