import os
import json
import yt_dlp
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

# --- 2. مسارات الويب للموقع والعداد ---
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

# --- 3. دالة التحميل الفعليه المطلوبة من bot.py مع تجاوز قيود تيك توك ---
def download_media(url, progress_callback=None):
    increment_downloads()

    def hook(d):
        if d['status'] == 'downloading' and progress_callback:
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            percent = (downloaded / total * 100) if total > 0 else 0
            speed = d.get('_speed_str', 'N/A')
            progress_callback(percent, speed)

    ydl_opts = {
        'format': 'best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'progress_hooks': [hook],
        'quiet': True,
        'no_warnings': True,
        # خيارات تجاوز حماية تيك توك والقيود
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'extractor_args': {
            'tiktok': {
                'webpage_download': True,
            }
        }
    }

    os.makedirs('downloads', exist_ok=True)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
