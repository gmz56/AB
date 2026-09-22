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
WEB_SITE_URL = os.getenv("WEB_SITE_URL", "https://ab-rbx9.onrender.com")

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
# 4. قاعدة بيانات الخلفيات الـ 20 المباشرة
# ==========================================
WALLPAPERS_DB = {
    "movies": [
        {"id": 1, "title": "Ragnar Lothbrok - Vikings", "url": "https://picsum.photos/id/1015/1200/800"},
        {"id": 2, "title": "Dexter - Tonight's The Night", "url": "https://picsum.photos/id/1018/1200/800"},
        {"id": 3, "title": "The Mentalist - Patrick Jane", "url": "https://picsum.photos/id/1025/1200/800"},
        {"id": 4, "title": "Walter White - Breaking Bad", "url": "https://picsum.photos/id/1069/1200/800"},
        {"id": 5, "title": "Thomas Shelby - Peaky Blinders", "url": "https://picsum.photos/id/1062/1200/800"},
        {"id": 6, "title": "Eleven - Stranger Things (The Void)", "url": "https://picsum.photos/id/1043/1200/800"},
        {"id": 7, "title": "Eminem - The King", "url": "https://picsum.photos/id/1031/1200/800"},
        {"id": 8, "title": "Billie Eilish - Dark Spider", "url": "https://picsum.photos/id/1035/1200/800"}
    ],
    "anime": [
        {"id": 9, "title": "العين الحمراء المتوهجة", "url": "https://picsum.photos/id/1067/1200/800"},
        {"id": 10, "title": "وجه المانغا بالأبيض والأسود", "url": "https://picsum.photos/id/1074/1200/800"},
        {"id": 11, "title": "فتاة الشعر الأبيض والزهرة", "url": "https://picsum.photos/id/1080/1200/800"},
        {"id": 12, "title": "فتاة الشعر الأبيض والعيون الحادة", "url": "https://picsum.photos/id/1084/1200/800"},
        {"id": 13, "title": "العيون الكريستالية الزرقاء", "url": "https://picsum.photos/id/1027/1200/800"},
        {"id": 14, "title": "العيون الخضراء المضيئة", "url": "https://picsum.photos/id/1050/1200/800"},
        {"id": 15, "title": "فان التخييم تحت سماء الليل والقمر", "url": "https://picsum.photos/id/1059/1200/800"}
    ],
    "dark": [
        {"id": 16, "title": "الشخصية الغامضة خلف السلاسل", "url": "https://picsum.photos/id/1040/1200/800"},
        {"id": 17, "title": "التأمل وسط البحر والضباب", "url": "https://picsum.photos/id/1053/1200/800"},
        {"id": 18, "title": "المجسم الكرومي اللامع", "url": "https://picsum.photos/id/1060/1200/800"},
        {"id": 19, "title": "التاج الأسود والغموض", "url": "https://picsum.photos/id/1011/1200/800"},
        {"id": 20, "title": "فتاة الهودي والعيون الحمراء", "url": "https://picsum.photos/id/1068/1200/800"}
    ]
}

# ==========================================
# 5. بناء لوحة القائمة الرئيسية والترحيب
# ==========================================
WELCOME_TEXT = (
    "🇸🇦 **كل عام والوطن بألف خير | اليوم الوطني السعودي 96** 🇸🇦\n\n"
    "أهلاً بك في بوت سلنقح للتحميل والمسح الذكي المجاني! ⚡\n\n"
    "• أرسل رابط الفيديو للتحميل المباشر خالي من الحقوق.\n"
    "• أو استخدم الموقع لمسح الكتابة والنصوص بالذكاء الاصطناعي مجاناً! 💚\n\n"
    "🛡 حقوق البرمجة والتطوير محفوظة لمطور الخدمة ©"
)

def get_main_keyboard(user_id):
    ref_count = get_user_ref_count(user_id)
    keyboard = [
        [InlineKeyboardButton("🚀 زيارة موقع التحميل والمسح الذكي", url=WEB_SITE_URL)],
        [InlineKeyboardButton("🎨 إنشاء بطاقة تهنئة باليوم الوطني", callback_data="cmd_card")],
        [InlineKeyboardButton("🖼 قسم خلفيات 4K عالية الدقة (20)", callback_data="wp_main")],
        [InlineKeyboardButton(f"🎁 رابط الدعوة الخاص بك ({ref_count} مدعوين)", callback_data="cmd_ref")],
        [InlineKeyboardButton("📜 شروط الاستخدام وإخلاء المسؤولية", callback_data="cmd_terms")],
        [InlineKeyboardButton("🟢 مشاركة البوت مع الأصدقاء", switch_inline_query="🚀 جرب بوت سلنقح المباشر لتحميل المقاطع واستعراض خلفيات الـ 4K!")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==========================================
# 6. دالة معالجة وإرسال الصورة المباشرة
# ==========================================
async def send_wallpaper_item(query, item):
    title = item["title"]
    file_path = item.get("file")
    url = item.get("url")

    # 1. إذا كان الملف موجوداً محلياً
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "rb") as photo_file:
                await query.message.reply_photo(
                    photo=photo_file,
                    caption=f"🖼 **{title}**\n\n✨ بدقة عالية 4K",
                    parse_mode="Markdown"
                )
                return
        except Exception as e:
            logger.error(f"Error sending local file: {e}")

    # 2. إرسال الصورة مباشرة عبر البث المباشر
    if url:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.get(url, headers=headers, timeout=12)
            if response.status_code == 200:
                bio = BytesIO(response.content)
                bio.name = "wallpaper.jpg"
                await query.message.reply_photo(
                    photo=bio,
                    caption=f"🖼 **{title}**\n\n✨ بدقة عالية 4K",
                    parse_mode="Markdown"
                )
                return
        except Exception as e:
            logger.error(f"Error downloading photo url: {e}")

    await query.message.reply_text(f"🖼 **{title}**\n\n✨ بدقة عالية 4K")

# ==========================================
# 7. دوال الأوامر والتحكم الرئيسي
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
        await query.edit_message_text(
            WELCOME_TEXT,
            reply_markup=get_main_keyboard(user_id),
            parse_mode="Markdown"
        )

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
            "1. هذا البوت مخصص للاستخدام الشخصي والمجاني فقط.\n"
            "2. يخلي المطور مسؤوليته الكاملة عن أي استخدام غير قانوني للمحتوى المحمل.\n"
            "3. جميع حقوق البرمجة والتطوير محفوظة لمطور الخدمة ©."
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="cmd_main")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "wp_main":
        keyboard = [
            [InlineKeyboardButton("🎬 شخصيات ومسلسلات (8)", callback_data="wp_cat_movies")],
            [InlineKeyboardButton("🎨 أنمي وفن رقمي (7)", callback_data="wp_cat_anime")],
            [InlineKeyboardButton("🌌 أنماط داكنة وغموض (5)", callback_data="wp_cat_dark")],
            [InlineKeyboardButton("🔙 العودة لقائمة الخدمات", callback_data="cmd_main")]
        ]
        text = "🎨 **قسم الخلفيات عالية الدقة (4K):**\n\nاختر التصنيف المفضل لديك:"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("wp_cat_"):
        category = data.split("_")[2]
        items = WALLPAPERS_DB.get(category, [])
        keyboard = []
        for item in items:
            keyboard.append([InlineKeyboardButton(item["title"], callback_data=f"wp_img_{category}_{item['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 العودة لقائمة الخلفيات", callback_data="wp_main")])
        
        await query.edit_message_text("🖼 **اختر الخلفية التي تريدها:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("wp_img_"):
        _, _, category, img_id = data.split("_")
        img_id = int(img_id)
        item = next((x for x in WALLPAPERS_DB.get(category, []) if x["id"] == img_id), None)
        if item:
            await send_wallpaper_item(query, item)

# ==========================================
# 8. صناعة البطاقات (Card Generation / PIL)
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
# 9. الاستعلام الفوري Inline Query Handler
# ==========================================
async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = [
        InlineQueryResultArticle(
            id="1",
            title="مشاركة بوت اليوم الوطني والتحميل",
            input_message_content=InputTextMessageContent(
                "🇸🇦 جرب بوت سلنقح المجاني للتحميل ومسح الذكاء الاصطناعي وخلفيات 4K!"
            )
        )
    ]
    await update.inline_query.answer(results)

# ==========================================
# 10. معالجة الرسائل والروابط (yt_dlp)
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
# 11. دالة التشغيل الرئيسية Main
# ==========================================
def main():
    keep_alive()

    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

    bot_app = Application.builder().token(TOKEN).build()

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("card", card_command))
    bot_app.add_handler(CommandHandler("wallpapers", start))
    bot_app.add_handler(CallbackQueryHandler(main_callback_handler))
    bot_app.add_handler(InlineQueryHandler(inline_query_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🤖 البوت يعمل بنجاح ومستعد لاستقبال الأوامر...")
    bot_app.run_polling()

if __name__ == "__main__":
    main()
