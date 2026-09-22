import os
import logging
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ==========================================
# 1. إعداد سيرفر Flask لضمان استمرار التشغيل
# ==========================================
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# ==========================================
# 2. إعدادات البوت والتوكن
# ==========================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ضع التوكن الخاص بك هنا
BOT_TOKEN = os.getenv("BOT_TOKEN", "ضع_التوكين_الخاص_بك_هنا")

# ==========================================
# 3. قاعدة بيانات الخلفيات الـ 15
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
# 4. دوال التحكم والأوامر
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎬 مسلسلات وسينما (3)", callback_data="wp_cat_movies")],
        [InlineKeyboardButton("🎨 أنمي وفن رقمي (7)", callback_data="wp_cat_anime")],
        [InlineKeyboardButton("🌌 أنماط داكنة وفضاء (5)", callback_data="wp_cat_dark")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🎨 **أهلاً بك في بوت الخلفيات (4K)!**\n\nاختر التصنيف لعرض الخلفيات:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data.startswith("wp_cat_"):
        category = data.split("_")[2]
        items = WALLPAPERS_DB.get(category, [])
        
        keyboard = []
        for item in items:
            keyboard.append([InlineKeyboardButton(item["title"], callback_data=f"wp_img_{category}_{item['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="wp_main")])
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
        await start(update, context)

# ==========================================
# 5. تشغيل البوت
# ==========================================
if __name__ == "__main__":
    # تشغيل سيرفر الويب في الخلفية
    keep_alive()
    
    # تشغيل البوت
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("wallpapers", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 البوت يعمل بنجاح...")
    app.run_polling()
