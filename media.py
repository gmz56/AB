import os
import json
import sys
from flask import Flask, jsonify

app = Flask(__name__)
STATS_FILE = "stats.json"

# --- 1. إدارة العداد والإحصائيات ---
def load_stats():
    if not os.path.exists(STATS_FILE):
        return 0
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("downloads", 0)
    except Exception:
        return 0

def increment_downloads():
    current_count = load_stats() + 1
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
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

# --- 3. دالة التحميل مع معالجة حماية المخرجات ---
def download_media(*args, **kwargs):
    try:
        # إصلاح وتوجيه المخرجات القياسية لمنع خطأ Errno 9 في Render
        if sys.stdout is None or sys.stdout.closed or sys.stdout.fileno() < 0:
            sys.stdout = open(os.devnull, 'w')
        if sys.stderr is None or sys.stderr.closed or sys.stderr.fileno() < 0:
            sys.stderr = open(os.devnull, 'w')
    except Exception:
        pass

    # زيادة العداد عند طلب التحميل
    increment_downloads()
    return True

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
