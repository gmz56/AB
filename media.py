import os
import json
import zipfile
import yt_dlp
from flask import Flask, jsonify, render_template_string, request, send_file, after_this_request

app = Flask(__name__)
STATS_FILE = "stats.json"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123456") # كلمة سر لوحة التحكم

# --- تصميم واجهة المستخدم (HTML) ---
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مُحمّل الفيديوهات والصور الشامل</title>
    <style>
        * { box-sizing: border-box; font-family: system-ui, -apple-system, sans-serif; }
        body { background: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }
        .card { background: #1e293b; padding: 30px; border-radius: 16px; width: 100%; max-width: 500px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); text-align: center; }
        h1 { margin-bottom: 10px; font-size: 24px; color: #38bdf8; }
        .platforms { font-size: 13px; color: #94a3b8; margin-bottom: 15px; }
        .stats-badge { background: #0284c7; color: #fff; padding: 6px 14px; border-radius: 20px; font-size: 14px; display: inline-block; margin-bottom: 20px; }
        input[type="text"], select { width: 100%; padding: 14px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #fff; font-size: 16px; margin-bottom: 14px; outline: none; }
        button { width: 100%; padding: 14px; border-radius: 8px; border: none; background: #0284c7; color: #fff; font-size: 16px; font-weight: bold; cursor: pointer; transition: background 0.2s; margin-bottom: 10px; }
        button:hover { background: #0369a1; }
        button:disabled { background: #475569; cursor: not-allowed; }
        .share-btn { background: #10b981; }
        .share-btn:hover { background: #059669; }
        #status { margin-top: 15px; font-size: 14px; color: #94a3b8; line-height: 1.5; }
    </style>
</head>
<body>
    <div class="card">
        <h1>🚀 مُحمّل الفيديوهات والميديا</h1>
        <div class="platforms">تيك توك • يوتيوب • إنستغرام • سناب شات • إكس</div>
        <div class="stats-badge">إجمالي التحميلات: <span id="count">...</span></div>
        
        <input type="text" id="videoUrl" placeholder="أدخل رابط المقطع أو ألبوم الصور..." />
        
        <select id="formatType">
            <option value="video_best">فيديو بأعلى جودة (MP4)</option>
            <option value="video_low">فيديو بجودة متوسطة (توفير البيانات)</option>
            <option value="audio_only">صوت فقط (MP3)</option>
        </select>
        
        <button id="downloadBtn" onclick="startDownload()">تحميل المحتوى</button>
        <button class="share-btn" onclick="copySiteLink()">📋 مشاركة الموقع</button>
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

        function copySiteLink() {
            navigator.clipboard.writeText(window.location.href);
            alert("تم نسخ رابط الموقع بنجاح!");
        }

        async function startDownload() {
            const urlInput = document.getElementById('videoUrl');
            const formatSelect = document.getElementById('formatType');
            const btn = document.getElementById('downloadBtn');
            const status = document.getElementById('status');
            const url = urlInput.value.trim();

            if (!url) {
                status.innerText = "⚠️ يرجى إدخال الرابط أولاً!";
                return;
            }

            btn.disabled = true;
            status.innerText = "⏳ جاري جلب وتجهيز المحتوى...";

            try {
                const response = await fetch('/api/download', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url, format_type: formatSelect.value })
                });

                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.error || "فشل التحميل من المصدر");
                }

                status.innerText = "✅ جاري التنزيل إلى جهازك...";
                const blob = await response.blob();
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = response.headers.get('Content-Disposition')?.split('filename=')[1]?.replace(/"/g, '') || "download_media";
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

# --- لوحة تحكم المشرف (HTML) ---
ADMIN_LAYOUT = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>لوحة التحكم - الإحصائيات</title>
    <style>
        body { background: #0f172a; color: #fff; font-family: system-ui; padding: 40px; text-align: center; }
        .box { background: #1e293b; max-width: 400px; margin: 0 auto; padding: 30px; border-radius: 12px; }
        h2 { color: #38bdf8; }
        .num { font-size: 48px; font-weight: bold; color: #10b981; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="box">
        <h2>📊 لوحة تحكم المشرف</h2>
        <p>إجمالي التنزيلات الناجحة:</p>
        <div class="num">{{ downloads }}</div>
        <p>حالة السيرفر: <span style="color: #10b981;">شغال 100%</span></p>
    </div>
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
    response = jsonify({"status": "online", "downloads": load_stats()})
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response

# لوحة التحكم للمشرف (اقتراح #3)
@app.route('/admin', methods=['GET'])
def admin_panel():
    pwd = request.args.get('pass', '')
    if pwd != ADMIN_PASSWORD:
        return "❌ كلمة المرور غير صحيحة! استخدم /admin?pass=YOUR_PASSWORD", 403
    return render_template_string(ADMIN_LAYOUT, downloads=load_stats())

@app.route('/api/download', methods=['POST'])
def web_download():
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    fmt_type = data.get('format_type', 'video_best')
    
    if not url:
        return jsonify({"error": "الرابط مطلوب"}), 400

    try:
        result = download_media(url, format_type=fmt_type)
        
        # إذا كانت النتيجة قائمة ملفات (ألبوم صور)
        if isinstance(result, list):
            zip_filename = "downloads/photos_album.zip"
            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                for f in result:
                    if os.path.exists(f):
                        zipf.write(f, os.path.basename(f))
            file_path = zip_filename
        else:
            file_path = result

        if not file_path or not os.path.exists(file_path):
            return jsonify({"error": "فشل حفظ الملف على السيرفر"}), 500

        @after_this_request
        def remove_file(response):
            try:
                if isinstance(result, list):
                    for f in result:
                        if os.path.exists(f): os.remove(f)
                    if os.path.exists(zip_filename): os.remove(zip_filename)
                elif os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
            return response

        return send_file(file_path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 3. دالة التحميل المحدثة (تأخذ نوع الجودة وتدعم ألبومات الصور) ---
def download_media(url, progress_callback=None, format_type="video_best"):
    increment_downloads()

    def hook(d):
        if d['status'] == 'downloading' and progress_callback:
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            percent = (downloaded / total * 100) if total > 0 else 0
            speed = d.get('_speed_str', 'N/A')
            progress_callback(percent, speed)

    format_opt = 'best'
    if format_type == "video_low":
        format_opt = 'worstvideo+worstaudio/worst'
    elif format_type == "audio_only":
        format_opt = 'bestaudio/best'

    ydl_opts = {
        'format': format_opt,
        'outtmpl': 'downloads/%(id)s_%(autonumber)s.%(ext)s',
        'progress_hooks': [hook],
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }

    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"

    os.makedirs('downloads', exist_ok=True)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        
        # دعم ألبوم الصور (اقتراح #4)
        if 'entries' in info and len(info['entries']) > 1:
            files = []
            for entry in info['entries']:
                if entry:
                    fname = ydl.prepare_filename(entry)
                    if os.path.exists(fname):
                        files.append(fname)
            return files if files else ydl.prepare_filename(info['entries'][0])
        elif 'entries' in info and len(info['entries']) == 1:
            return ydl.prepare_filename(info['entries'][0])
        else:
            return ydl.prepare_filename(info)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
