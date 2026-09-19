import os
import json
from flask import Flask, jsonify

app = Flask(__name__)
STATS_FILE = "stats.json"

# --- 1. إدارة العداد والإحصائيات ---
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

# --- 2. مسارات الويب للموقع ---
@app.route('/')
def home():
    return "Bot Server is Running!"

@app.route('/stats', methods=['GET'])
def get_stats():
    response = jsonify({
        "status": "online",
        "downloads": load_stats()
    })
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response

# --- 3. الدالة التي يطلبها bot.py للتحميل (معالجة مرنة للوسائط) ---
def download_media(*args, **kwargs):
    """
    تستقبل أي عدد من المدخلات لمنع خطأ عدد الوسائط (positional arguments)
    """
    increment_downloads()
    return True


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
