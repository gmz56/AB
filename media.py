import os
import json
from flask import Flask, jsonify

app = Flask(__name__)
STATS_FILE = "stats.json"

# --- 1. إدارة العداد والإحصائيات بشكل آمن ---
def load_stats():
    if not os.path.exists(STATS_FILE):
        return 0
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("downloads", 0)
    except Exception as e:
        print(f"Error reading stats: {e}")
        return 0

def increment_downloads():
    current_count = load_stats() + 1
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump({"downloads": current_count}, f)
            f.flush()
            os.fsync(f.fileno())
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

# --- 3. الدالة التي يطلبها bot.py للتحميل ---
def download_media(*args, **kwargs):
    increment_downloads()
    return True

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
