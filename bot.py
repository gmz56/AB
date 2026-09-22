import os
import json
import logging
import gc
import requests
import time
import base64
import yt_dlp
from io import BytesIO
from threading import Thread
from flask import Flask, render_template_string, request, jsonify
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
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
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# إعدادات السجلات Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# 1. إعداد سيرفر Flask للاستضافة على Render
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running online!"

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
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")

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
# 4. قاعدة بيانات الخلفيات الـ 15 (4K)
# ==========================================
WALLPAPERS_DB = {
    "movies": [
        {"id": 1, "title": "Ragnar Lothbrok - Vikings", "url": "https://your-domain.com/images/vikings.jpg"},
        {"id": 2, "title": "Dexter - Tonight's The Night", "url": "https://your-domain.com/images/dexter.jpg"},
        {"id": 3, "title": "The Mentalist - Patrick Jane", "url": "https://your-domain.com/images/mentalist.jpg"}
    ],
    "anime": [
        {"id": 4, "title": "العين الحمراء المتوهجة", "url": "https://your-domain.com/images/red_eye.jpg"},
        {"id": 5, "title": "شاب على السيارة تحت سماء الليل", "url": "https://your-domain.com/images/boy_car.jpg"},
        {"id": 6, "title": "فتاة حقل اليراعات عند الغروب", "url": "https://your-domain.com/images/fireflies.jpg"},
        {"id": 7, "title": "فتاة النافذة والمطر", "url": "https://your-domain.com/images/window_rain.jpg"},
        {"id": 8, "title": "وجه المانغا بالأبيض والأسود", "url": "https://your-domain.com/images/manga_face.jpg"},
        {"id": 9, "title": "فان التخييم تحت سماء الليل والقمر", "url": "https://your-domain.com/images/camper_van.jpg"},
        {"id": 10, "title": "فتاة الشعر الأبيض والزهرة", "url": "https://your-domain.com/images/white_hair.jpg"}
    ],
    "dark": [
        {"id": 11, "title": "الكسوف والكوكب فوق الجبال", "url": "https://your-domain.com/images/eclipse.jpg"},
        {"id": 12, "title": "الشخصية الغامضة والتاج الأسود", "url": "https://your-domain.com/images/black_crown.jpg"},
        {"id": 13, "title": "التأمل وسط البحر والضباب", "url": "https://your-domain.com/images/sea_meditation.jpg"},
        {"id": 14, "title": "المجسم الكرومي اللامع", "url": "https://your-domain.com/images/chrome.jpg"},
        {"id": 15, "title": "الشخصية الغامضة خلف السلاسل", "url": "https://your-domain.com/images/chains.jpg"}
    ]
}

# ==========================================
# 5. دوال قسم الخلفيات
# ==========================================
async def wallpapers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎬 مسلسلات وسينما (3)", callback_data="wp_cat_movies")],
        [InlineKeyboardButton("🎨 أنمي وفن رقمي (7)", callback_data="wp_cat_anime")],
        [InlineKeyboardButton("🌌 أنماط داكنة وفضاء (5)", callback_data="wp_cat_dark")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🎨 **قسم الخلفيات عالية الدقة (4K):**\n\nاختر التصنيف المفضل لديك:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def wallpapers_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if not data.startswith("wp_"):
        return

    await query.answer()

    if data.startswith("wp_cat_"):
        category = data.split("_")[2]
        items = WALLPAPERS_DB.get(category, [])
        
        keyboard = []
        for item in items:
            keyboard.append([InlineKeyboardButton(item["title"], callback_data=f"wp_img_{category}_{item['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 العودة لقائمة الخلفيات", callback_data="wp_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text("🖼 **اختر الخلفية التي تريدها:**", reply_markup=reply_markup, parse_mode="Markdown")

    elif data.startswith("wp_img_"):
        _, _, category, img_id = data.split("_")
        img_id = int(img_id)
        
        item = next((x for x in WALLPAPERS_DB[category] if x["id"] == img_id), None)
        if item:
            await query.message.reply_photo(
                photo=item["url"],
                caption=f"🖼 **{item['title']}**\n\n✨ بدقة عالية 4K",
                parse_mode="Markdown"
            )

    elif data == "wp_main":
        await wallpapers_command(update, context)

# ==========================================
# 6. صناعة البطاقات (Card Generation / PIL)
# ==========================================
def create_card_image(text_content):
    if not HAS_PIL:
        return None
    img = Image.new('RGB', (800, 400), color=(30, 30, 30))
    d = ImageDraw.Draw(img)
    d.text((50, 180), f"Card: {text_content}", fill=(255, 255, 255))
    bio = BytesIO()
    bio.name = 'card.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

async def card_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = " ".join(context.args) if context.args else "معايدة خاصة"
    msg = await update.message.reply_text("🎨 جاري تصميم البطاقة...")
    
    bio = create_card_image(user_text)
    if bio:
        await update.message.reply_photo(photo=bio, caption=f"🖼 **بطاقتك جاهزة:** {user_text}")
        await msg.delete()
    else:
        await msg.edit_text(f"🖼 **بطاقتك:** {user_text}")

# ==========================================
# 7. الاستعلام الفوري Inline Query Handler
# ==========================================
async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    results = [
        InlineQueryResultArticle(
            id="1",
            title="مشاركة بوت التنزيل والخلفيات",
            input_message_content=InputTextMessageContent(
                "🤖 استخدم هذا البوت لتحميل المقاطع واستعراض أجمل خلفيات الـ 4K!"
            )
        )
    ]
    await update.inline_query.answer(results)

# ==========================================
# 8. دوال الأوامر والتحميل (Start & Download)
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        save_user(update.effective_user.id)
        
        # معالجة رابط الإحالة إن وجد
        if context.args:
            referrer_id = context.args[0]
            if referrer_id != str(update.effective_user.id):
                save_referral(referrer_id, update.effective_user.id)

    welcome_text = (
        "👋 **أهلاً بك في البوت الشامل!**\n\n"
        "🎬 **تحميل المقاطع:** أرسل رابط أي مقطع فيديو لتنزيله فوراً.\n"
        "💳 **صناعة البطاقات:** اكتب /card ثم نصك لتصميم بطاقة.\n"
        "🖼 **قسم الخلفيات:** اكتب /wallpapers لعرض أجمل خلفيات 4K."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    if update.effective_user:
        save_user(update.effective_user.id)

    # التحقق مما إذا كان المدخل رابطاً للتحميل
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
        await update.message.reply_text("💡 أرسل رابط مقطع فيديو لتحميله، أو استخدم /wallpapers للخلفيات، أو /card للبطاقات.")

# ==========================================
# 9. دالة التشغيل الرئيسية Main
# ==========================================
def main():
    keep_alive()

    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

    bot_app = Application.builder().token(TOKEN).build()

    # تسجيل كافة الأوامر والمُعالجات (Handlers)
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("card", card_command))
    bot_app.add_handler(CommandHandler("wallpapers", wallpapers_command))
    bot_app.add_handler(CallbackQueryHandler(wallpapers_callback_handler, pattern="^wp_"))
    bot_app.add_handler(InlineQueryHandler(inline_query_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🤖 البوت يعمل بنجاح ومستعد لاستقبال الأوامر...")
    bot_app.run_polling()

if __name__ == "__main__":
    main()
