import os
import json
import logging
from flask import Flask, jsonify
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- إعداد خادم Flask ---
app = Flask(__name__)
STATS_FILE = "stats.json"

def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f:
                return json.load(f).get("downloads", 0)
        except Exception:
            return 0
    return 0

def increment_downloads():
    current_count = load_stats() + 1
    try:
        with open(STATS_FILE, "w") as f:
            json.dump({"downloads": current_count}, f)
    except Exception as e:
        print(f"Error saving stats: {e}")
    return current_count

@app.route('/')
def home():
    return "Bot Server is Running!"

@app.route('/stats', methods=['GET'])
def get_stats():
    return jsonify({"status": "online", "downloads": load_stats()})


# --- أوامر ووظائف تليجرام للبوت ---
TOKEN = os.environ.get("BOT_TOKEN", "ضع_توكن_البوت_هنا_إن_لم_يكن_في_المتغيرات")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك في بوت سلنقح للتحميل السريع!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    # هنا يتم التحميل وإرسال الفيديو للمستخدم
    await update.message.reply_text("جاري التحميل...")
    
    # زيادة العداد عند إتمام التحميل
    increment_downloads()


if __name__ == '__main__':
    # تشغيل سيرفر Flask للبوت
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
