import os
import json
import threading
from flask import Flask, jsonify

# --- 1. خادم Flask والإحصائيات ---
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

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# تشغيل سيرفر Flask في الخلفية لكي لا يعطل البوت
threading.Thread(target=run_flask, daemon=True).start()

# --- 2. كود البوت الخاص بك يبدأ من هنا ---
# أضف دالة increment_downloads() بعد أي عملية إرسال فيديو ناجحة للمستخدم
