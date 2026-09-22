import os
import json
import logging
import time
import subprocess
import yt_dlp
from io import BytesIO
from threading import Thread
from flask import Flask, send_from_directory, render_template_string
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
# 1. إعداد سيرفر Flask والواجهة الرسمية للموقع
# ==========================================
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>منصة وبوت سلنقح | للتحميل وتوضيح المقاطع 🇸🇦</title>
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
        .hero-section {
            padding: 70px 20px 40px;
            text-align: center;
        }
        .brand-badge {
            background: rgba(25, 135, 84, 0.2);
            border: 1px solid #198754;
            color: #2ecc71;
            padding: 8px 20px;
            border-radius: 50px;
            font-size: 0.95rem;
            display: inline-block;
            margin-bottom: 25px;
        }
        .hero-title {
            font-size: 2.6rem;
            font-weight: 900;
            margin-bottom: 20px;
            background: linear-gradient(45deg, #2ecc71, #ffffff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .hero-subtitle {
            color: #a0aec0;
            font-size: 1.15rem;
            max-width: 650px;
            margin: 0 auto 35px;
            line-height: 1.8;
        }
        .btn-green {
            background: #198754;
            color: white;
            font-weight: 700;
            padding: 14px 32px;
            border-radius: 12px;
            text-decoration: none;
            transition: all 0.3s ease;
            box-shadow: 0 10px 25px rgba(25, 135, 84, 0.4);
            display: inline-block;
        }
        .btn-green:hover {
            background: #146c43;
            color: white;
            transform: translateY(-3px);
        }
        .stat-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 25px;
            text-align: center;
            backdrop-filter: blur(10px);
        }
        .stat-number {
            font-size: 2.2rem;
            font-weight: 800;
            color: #2ecc71;
        }
        .feature-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            padding: 30px 20px;
            transition: all 0.3s ease;
            height: 100%;
        }
        .feature-card:hover {
            transform: translateY(-5px);
            border-color: #198754;
        }
        .feature-icon {
            font-size: 2.5rem;
            margin-bottom: 15px;
        }
        footer {
            margin-top: auto;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            padding: 25px 0;
            text-align: center;
            color: #718096;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>

    <div class="container hero-section">
        <div class="brand-badge">🇸🇦 منصة وبوت سلنقح الخدمية 🇸🇦</div>
        <h1 class="hero-title">المنصة الأولى للتحميل والتعديل الذكي المجاني</h1>
        <p class="hero-subtitle">
            قم بتحميل الفيديوهات من كافة منصات التواصل الاجتماعي بدون حقوق، بالإضافة لخدمة توضيح المقاطع ورفع الدقة مجاناً وبسرعة فائقة عبر البوت!
        </p>
        <div>
            <a href="https://t.me/{{ bot_username if bot_username else 'bot' }}" target="_blank" class="btn-green">
                🚀 فتح البوت المباشر في تيليجرام
            </a>
        </div>
    </div>

    <div class="container my-4">
        <div class="row g-4 justify-content-center">
            <div class="col-md-4">
                <div class="stat-card">
                    <div class="stat-number">{{ downloads_count }}</div>
                    <div class="text-secondary mt-1">عملية تحميل وتوضيح ناجحة</div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="stat-card">
                    <div class="stat-number">{{ users_count }}</div>
                    <div class="text-secondary mt-1">مستخدم نشط في الخدمة</div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="stat-card">
                    <div class="stat-number">🟢 أونلاين</div>
                    <div class="text-secondary mt-1">حالة السيرفر والخدمة</div>
                </div>
            </div>
        </div>
    </div>

    <div class="container my-5">
        <h3 class="text-center fw-bold mb-4">✨ مميزات الخدمة</h3>
        <div class="row g-4">
            <div class="col-md-4">
                <div class="feature-card text-center">
                    <div class="feature-icon">🎬</div>
                    <h5 class="fw-bold text-white mb-2">تحميل الفيديوهات</h5>
                    <p class="text-secondary mb-0">تحميل مباشر من تيك توك، انستقرام، يوتيوب، وباقي المنصات بدون علامة مائية.</p>
                </div>
            </div>
            <div class="col-md-4">
                <div class="feature-card text-center">
                    <div class="feature-icon">⚡</div>
                    <h5 class="fw-bold text-white mb-2">توضيح ورفع الدقة</h5>
                    <p class="text-secondary mb-0">معالجة الفيديوهات المحفوظة بجوالك وتوضيح معالمها وإزالة التغبيش مجاناً.</p>
                </div>
            </div>
            <div class="col-md-4">
                <div class="feature-card text-center">
                    <div class="feature-icon">🎨</div>
                    <h5 class="fw-bold text-white mb-2">بطاقات اليوم الوطني</h5>
                    <p class="text-secondary mb-0">إنشاء بطاقات تهنئة فورية باسمك بمناسبة اليوم الوطني السعودي 96.</p>
                </div>
            </div>
        </div>
    </div>

    <footer>
        <div class="container">
            <p class="mb-0">حقوق البرمجة والتطوير محفوظة لمطور الخدمة © 2026 | منصة سلنقح</p>
        </div>
    </footer>

</body>
</html>
"""

@app.route('/')
def home():
    stats = get_stats()
    users = set()
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                users = set(json.load(f))
        except:
            pass
    bot_name = os.getenv("BOT_USERNAME", "")
    return render_template_string(
        HTML_TEMPLATE,
        downloads_count=stats.get("downloads", 0),
        users_count=len(users),
        bot_username=bot_name
    )

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# 2. البيانات والمتغيرات العامة
# ==========================================
COUNTER_FILE = "stats.json"
USERS_FILE = "users.json"
REFERRALS_FILE = "referrals.json"

ADMIN_ID = os.getenv("ADMIN_ID")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
WEB_SITE_URL = os.getenv("WEB_SITE_URL", "https://ab-rbx9.onrender.com").rstrip('/')

# ==========================================
# 3. إدارة الإحصائيات والمستخدمين والإحالات
# ==========================================
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

def get_referrals():
    if os.path.exists(REFERRALS_FILE):
        try:
            with open(REFERRALS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def get_user_ref_count(user_id):
    refs = get_referrals()
    return len(refs.get(str(user_id), []))

def save_referral(referrer_id, referred_id):
    refs = get_referrals()
    key = str(referrer_id)
    if key not in refs:
        refs[key] = []
    if referred_id not in refs[key]:
        refs[key].append(referred_id)
        with open(REFERRALS_FILE, 'w') as f:
            json.dump(refs, f)

# ==========================================
# 4. بناء لوحة القائمة الرئيسية والترحيب
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
        [InlineKeyboardButton("🚀 زيارة موقع الخدمة", url=WEB_SITE_URL)],
        [InlineKeyboardButton("🎨 إنشاء بطاقة تهنئة باليوم الوطني", callback_data="cmd_card")],
        [InlineKeyboardButton(f"🎁 رابط الدعوة الخاص بك ({ref_count} مدعوين)", callback_data="cmd_ref")],
        [InlineKeyboardButton("📜 شروط الاستخدام وإخلاء المسؤولية", callback_data="cmd_terms")],
        [InlineKeyboardButton("🟢 مشاركة البوت مع الأصدقاء", switch_inline_query="🚀 جرب بوت سلنقح للتحميل وتوضيح المقاطع مجاناً!")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==========================================
# 5. دوال التحكم والقائمة الرئيسية
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    if context.args:
        referrer_id = context.args[0]
        if referrer_id != str(user_id):
            save_referral(referrer_id, user_id)

    reply_markup = get_main_keyboard(user_id)
    await update.message.reply_text(WELCOME_TEXT, reply_markup=reply_markup, parse_mode="Markdown")

async def main_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    bot_username = context.bot.username or "bot"
    await query.answer()

    if data == "cmd_main":
        await query.edit_message_text(WELCOME_TEXT, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

    elif data == "cmd_card":
        text = (
            "🎨 **إنشاء بطاقة تهنئة باليوم الوطني:**\n\n"
            "لإنشاء بطاقتك الخاصة، اكتب الأمر `/card` متبوعاً بالاسم أو النص المفضل لديك.\n\n"
            "**مثال:**\n`/card كل عام والوطن بخير - سلمان`"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="cmd_main")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "cmd_ref":
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        ref_count = get_user_ref_count(user_id)
        text = (
            f"🎁 **رابط الدعوة الخاص بك:**\n\n"
            f"`{ref_link}`\n\n"
            f"📊 **عدد المدعوين لديك:** `{ref_count}` شخص.\n"
            f"قم بنشر الرابط بين أصدقائك لاستخدام البوت المباشر!"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="cmd_main")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "cmd_terms":
        text = (
            "📜 **شروط الاستخدام وإخلاء المسؤولية:**\n\n"
            "1. هذا البوت مخصص للاستخدام الشخصي والمجاني 100%.\n"
            "2. يخلي المطور مسؤوليته الكاملة عن أي استخدام غير قانوني للمحتوى المحمل.\n"
            "3. جميع حقوق البرمجة والتطوير محفوظة لمطور الخدمة ©."
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="cmd_main")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

# ==========================================
# 6. التوضيح والمُعالجة السريعة والآمنة (FFmpeg Fixed Dimensions)
# ==========================================
async def handle_video_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)

    status_msg = await update.message.reply_text("⚡ **جاري تنزيل الفيديو وتوضيحه بسرعة...**")

    input_path = None
    output_path = None

    try:
        video_obj = update.message.video or update.message.document
        
        if hasattr(video_obj, 'file_size') and video_obj.file_size > 20 * 1024 * 1024:
            await status_msg.edit_text("⚠️ **حجم الفيديو يتجاوز 20 ميجابايت.** يرجى إرسال مقطع بحجم أصغر.")
            return

        video_file = await context.bot.get_file(video_obj.file_id)
        
        timestamp = int(time.time())
        input_path = os.path.join(UPLOAD_FOLDER, f"in_{user_id}_{timestamp}.mp4")
        output_path = os.path.join(UPLOAD_FOLDER, f"out_{user_id}_{timestamp}.mp4")

        await video_file.download_to_drive(input_path)

        filter_str = "scale=w='trunc(iw*1.3/2)*2':h='trunc(ih*1.3/2)*2':flags=bicubic,unsharp=3:3:1.0:3:3:0.0,eq=contrast=1.05:saturation=1.1"

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", filter_str,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-threads", "0",
            "-c:a", "aac",
            "-b:a", "128k",
            output_path
        ]

        process = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if process.returncode == 0 and os.path.exists(output_path):
            increment_stats()
            await status_msg.edit_text("✅ **تمت المعالجة والتوضيح بنجاح! جاري إرسال المقطع...**")
            
            with open(output_path, 'rb') as video_out:
                await update.message.reply_video(
                    video=video_out,
                    caption="⚡ **تم رفع دقة الفيديو وتوضيح معالمه بنجاح!**"
                )
            await status_msg.delete()
        else:
            err_output = process.stderr.decode('utf-8', errors='ignore')
            logger.error(f"FFmpeg error details: {err_output}")
            await status_msg.edit_text("❌ متعذر معالجة هذا الفيديو، تأكد من إرسال مقطع فيديو صالح.")

    except Exception as e:
        logger.error(f"Error processing video: {e}")
        await status_msg.edit_text(f"❌ **حدث خطأ أثناء معالجة الفيديو:**\n`{str(e)}`", parse_mode="Markdown")
    
    finally:
        for p in [input_path, output_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass

# ==========================================
# 7. صناعة البطاقات (Card Generation / PIL)
# ==========================================
def create_card_image(text_content):
    if not HAS_PIL:
        return None
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

# ==========================================
# 8. الاستعلام الفوري Inline Query Handler
# ==========================================
async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = [
        InlineQueryResultArticle(
            id="1",
            title="مشاركة بوت اليوم الوطني والتحميل",
            input_message_content=InputTextMessageContent(
                "🇸🇦 جرب بوت سلنقح للتحميل وتوضيح الفيديوهات مجاناً بالكامل!"
            )
        )
    ]
    await update.inline_query.answer(results)

# ==========================================
# 9. معالجة النصوص والروابط (yt_dlp)
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    if update.effective_user:
        save_user(update.effective_user.id)

    if text.startswith("http://") or text.startswith("https://"):
        msg = await update.message.reply_text("⏳ جاري معالجة الرابط والتحميل...")
        try:
            ydl_opts = {
                'format': 'best',
                'outtmpl': 'downloaded_video.%(ext)s',
                'quiet': True,
                'no_warnings': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                filename = ydl.prepare_filename(info)

            increment_stats()
            with open(filename, 'rb') as video_file:
                await update.message.reply_video(video=video_file, caption="✅ تم التحميل بنجاح!")
            
            if os.path.exists(filename):
                os.remove(filename)
            await msg.delete()
        except Exception as e:
            logger.error(f"Error downloading: {e}")
            await msg.edit_text("❌ حدث خطأ أثناء تنزيل المقطع. تأكد من صحة الرابط.")
    else:
        await start(update, context)

# ==========================================
# 10. دالة التشغيل الرئيسية Main
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
    
    # معالج الفيديوهات المرفوعة
    bot_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video_upload))
    bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🤖 البوت يعمل بنجاح ومستعد لاستقبال المقاطع وتوضيحها بسرعة...")
    bot_app.run_polling()

if __name__ == "__main__":
    main()
