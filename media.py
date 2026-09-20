import os
import json
import yt_dlp
from flask import Flask, jsonify, render_template_string, request, send_file, after_this_request

app = Flask(__name__)
STATS_FILE = "stats.json"

# --- تصميم واجهة المستخدم (HTML) ---
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مُحمّل الفيديوهات والصور السريع</title>
    <style>
        * { box-sizing: border-box; font-family: system-ui, -apple-system, sans-serif; }
        body { background: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }
        .card { background: #1e293b; padding: 30px; border-radius: 16px; width: 100%; max-width: 500px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); text-align: center; }
        h1 { margin-bottom: 10px; font-size: 24px; color: #38bdf8; }
        .stats-badge { background: #0284c7; color: #fff; padding: 6px 14px; border-radius: 20px; font-size: 14px; display: inline-block; margin-bottom: 20px; }
        input[type="text"] { width: 100%; padding: 14px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #fff; font-size: 16px; margin-bottom: 16px; outline: none; }
        input[type="text"]:focus { border-color: #38bdf8; }
        button { width: 100%; padding: 14px; border-radius: 8px; border: none; background: #0284c7; color: #fff; font-size: 16px; font-weight: bold; cursor: pointer; transition: background 0.2s; }
        button:hover { background: #0369a1; }
        button:disabled { background: #475569; cursor: not-allowed; }
        #status { margin-top: 20px; font-size: 14px; color: #94a3b8; line-height: 1.5; }
    </style>
</head>
<body>
    <div class="card">
        <h1>🚀 مُحمّل الفيديوهات والصور</h1>
        <div class="stats-badge">إجمالي التحميلات: <span id="count">...</span></div>
        <input type="text" id="videoUrl" placeholder="أدخل رابط الفيديو أو ألبوم الصور..." />
        <button id="downloadBtn" onclick="startDownload()">تحميل المحتوى</button>
        <div id="status"></div>
    </div>

    <script>
        async function fetchStats() {
            try {
                const res = await fetch('/stats');
                const data = await res.json();
                document.getElementById('count').innerText = data.downloads || 0;
            } catch(e) {}
        }
        fetchStats();

        async function startDownload() {
            const urlInput = document.getElementById('videoUrl');
            const btn = document.getElementById('downloadBtn');
            const status = document.getElementById('status');
            const url = urlInput.value.trim();

            if (!url) {
                status.innerText = "⚠️ يرجى إدخال الرابط أولاً!";
                return;
            }

            btn.disabled = true;
            status.innerText = "⏳ جاري جلب المحتوى وتجهيزه...";

            try {
                const response = await fetch('/api/download', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });

                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.error || "فشل التحميل من المصدر");
                }

                status.innerText = "✅ جاري تنزيل الملف إلى جهازك...";
                const blob = await response.blob();
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = "media_download";
                document.body.appendChild(a);
                a.click();
                a.remove();
                status.innerText = "🎉 تم التحميل بنجاح!";
                fetchStats();
            } catch (err) {
                status.innerText = "❌ حدث خطأ: " + err.message;
            } finally {
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>
"""

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

# --- 2. مسارات الويب والموقع ---
@app.route('/')
def home():
    return render_template_string(HTML_LAYOUT)

@app.route('/stats', methods=['GET'])
def get_stats():
    response = jsonify({
        "status": "online",
        "downloads": load_stats()
    })
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response

@app.route('/api/download', methods=['POST'])
def web_download():
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({"error": "الرابط مطلوب"}), 400

    try:
        file_path = download_media(url)
        
        if not file_path or not os.path.exists(file_path):
            return jsonify({"error": "فشل حفظ الملف على السيرفر"}), 500

        @after_this_request
        def remove_file(response):
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
            return response

        return send_file(file_path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 3. دالة التحميل الفعليه المطلوبة (فيديو + صور) ---
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
        'format': 'best/bestvideo+bestaudio',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'progress_hooks': [hook],
        'quiet': True,
        'no_warnings': True,
        'concurrent_fragment_downloads': 5,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"

    os.makedirs('downloads', exist_ok=True)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        
        # في حال كان الرابط ألبوم صور/قائمة عناصر متعددة
        if 'entries' in info and len(info['entries']) > 0:
            filename = ydl.prepare_filename(info['entries'][0])
        else:
            filename = ydl.prepare_filename(info)
            
        return filename

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
