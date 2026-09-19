import os
import json
from flask import Flask, jsonify, request

app = Flask(__name__)

STATS_FILE = "stats.json"

# --- دالة قراءة الإحصائيات من الملف المحلي ---
def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f:
                data = json.load(f)
                return data.get("downloads", 0)
        except Exception:
            return 0
    return 0

# --- دالة زيادة العداد عند كل عملية تحميل ناجحة ---
def increment_downloads():
    current_count = load_stats() + 1
    try:
        with open(STATS_FILE, "w") as f:
            json.dump({"downloads": current_count}, f)
    except Exception as e:
        print(f"Error saving stats: {e}")
    return current_count

# --- مسارات Flask الأساسية ---

@app.route('/')
def home():
    return "Bot Server is Running!"

# مسار العداد المخصص لربطه بالموقع الإلكتروني
@app.route('/stats', methods=['GET'])
def get_stats():
    return jsonify({
        "status": "online",
        "downloads": load_stats()
    })

# --- معالجة منطق التنزيل والإرسال للبوت ---
def handle_download_and_send(chat_id, media_url):
    """
    ضع منطق التحميل الخاص بك هنا (تنزيل مقطع التيك توك أو الانستقرام)
    """
    # مثال لتنفيذ العملية:
    success = True  # افتراض نجاح عملية التحميل وإرسال الفيديو للمستخدم
    
    if success:
        # زيادة العداد تلقائياً بمقدار 1 عند كل تحميل ناجح
        increment_downloads()
        return True
    return False

if __name__ == '__main__':
    # تشغيل الخادم
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
