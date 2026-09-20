import os
import re
import json
import yt_dlp
from flask import Flask, render_template_string, request, jsonify, send_file

app = Flask(__name__)
COUNTER_FILE = "stats.json"

def get_stats():
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"downloads": 0}

def increment_stats():
    stats = get_stats()
    stats["downloads"] = stats.get("downloads", 0) + 1
    with open(COUNTER_FILE, 'w') as f:
        json.dump(stats, f)
    return stats["downloads"]

def get_media_info(url):
    ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'title': info.get('title', 'محتوى ميديا'),
            'thumbnail': info.get('thumbnail', ''),
            'duration': info.get('duration', 0),
            'uploader': info.get('uploader', 'غير معروف')
        }

def download_media(url, format_type="video_best"):
    increment_stats()
    output_template = 'downloads/%(id)s.%(ext)s'
    os.makedirs('downloads', exist_ok=True)

    if format_type == "audio_only":
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }
    elif format_type == "video_low":
        ydl_opts = {
            'format': 'worstvideo+worstaudio/worst',
            'outtmpl': output_template,
            'quiet': True,
        }
    else:
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': output_template,
            'quiet': True,
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if 'entries' in info:
            images = []
            for entry in info['entries']:
                filename = ydl.prepare_filename(entry)
                if os.path.exists(filename):
                    images.append(filename)
            return images
        else:
            filename = ydl.prepare_filename(info)
            if format_type == "audio_only":
                base, _ = os.path.splitext(filename)
                filename = base + ".mp3"
            return filename

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مُحمّل الميديا الاحترافي 🚀</title>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg-color: #0d1117;
            --card-bg: rgba(22, 27, 34, 0.85);
            --accent-gradient: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
            --button-green: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            --text-color: #f0f6fc;
            --text-secondary: #8b949e;
            --border-color: rgba(255, 255, 255, 0.12);
        }

        * { box-sizing: border-box; font-family: 'Tajawal', sans-serif; margin: 0; padding: 0; }

        body {
            background: #090d16;
            background-image: 
                radial-gradient(at 0% 0%, rgba(79, 172, 254, 0.2) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(0, 242, 254, 0.2) 0px, transparent 50%);
            color: var(--text-color);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }

        .container {
            background: var(--card-bg);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 35px 25px;
            width: 100%;
            max-width: 480px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.6);
            text-align: center;
        }

        h1 { font-size: 1.8rem; font-weight: 900; margin-bottom: 8px; color: #fff; }
        .sub-text { color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 20px; }

        .stat-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(79, 172, 254, 0.15);
            color: #4facfe;
            padding: 8px 18px;
            border-radius: 50px;
            font-size: 0.88rem;
            font-weight: 700;
            margin-bottom: 25px;
            border: 1px solid rgba(79, 172, 254, 0.3);
        }

        .input-group { margin-bottom: 15px; }

        input, select {
            width: 100%;
            padding: 14px 16px;
            background: rgba(13, 17, 23, 0.9);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            color: #fff;
            font-size: 0.95rem;
            outline: none;
            transition: all 0.3s ease;
        }

        input:focus, select:focus {
            border-color: #4facfe;
            box-shadow: 0 0 12px rgba(79, 172, 254, 0.3);
        }

        .btn {
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 12px;
            font-size: 1rem;
            font-weight: 700;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            margin-top: 10px;
        }

        .btn-main { background: var(--accent-gradient); color: #000; }
        .btn-share { background: var(--button-green); color: #000; }
        .btn:active { transform: scale(0.98); }

        .preview-card {
            display: none;
            background: rgba(0, 0, 0, 0.5);
            border-radius: 16px;
            padding: 15px;
            margin: 15px 0;
            border: 1px solid var(--border-color);
            text-align: right;
        }

        .preview-card img {
            width: 100%;
            height: 180px;
            object-fit: cover;
            border-radius: 12px;
            margin-bottom: 10px;
        }

        .preview-title {
            font-size: 0.95rem;
            font-weight: 700;
            color: #fff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .progress-box {
            display: none;
            margin: 15px 0;
        }

        .progress-bar-bg {
            background: rgba(255, 255, 255, 0.1);
            height: 10px;
            border-radius: 10px;
            overflow: hidden;
        }

        .progress-bar-fill {
            background: var(--accent-gradient);
            height: 100%;
            width: 0%;
            transition: width 0.4s ease;
        }

        .progress-text {
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-top: 6px;
        }
    </style>
</head>
<body>

<div class="container">
    <h1>🚀 مُحمّل الميديا الذكي</h1>
    <p class="sub-text">تيك توك • يوتيوب • إنستغرام • سناب شات • إكس</p>

    <div class="stat-badge">
        <i class="fa-solid fa-chart-line"></i>
        <span>إجمالي التحميلات: <span id="download-count">{{ downloads }}</span></span>
    </div>

    <div class="input-group">
        <input type="url" id="media-url" placeholder="أدخل رابط المقطع أو ألبوم الصور..." oninput="fetchPreview()">
    </div>

    <div class="preview-card" id="preview-box">
        <img id="preview-img" src="" alt="Thumbnail">
        <div class="preview-title" id="preview-title">جاري التجهيز...</div>
    </div>

    <div class="input-group">
        <select id="format-type">
            <option value="video_best">🎬 فيديو بأعلى جودة (MP4)</option>
            <option value="video_low">📱 فيديو جودة متوسطة (توفير بيانات)</option>
            <option value="audio_only">🎵 صوت فقط (MP3)</option>
        </select>
    </div>

    <div class="progress-box" id="progress-box">
        <div class="progress-bar-bg">
            <div class="progress-bar-fill" id="progress-fill"></div>
        </div>
        <div class="progress-text" id="progress-status">جاري التحميل...</div>
    </div>

    <button class="btn btn-main" onclick="startDownload()">
        <i class="fa-solid fa-download"></i> تحميل المحتوى
    </button>

    <button class="btn btn-share" onclick="shareSite()">
        <i class="fa-solid fa-share-nodes"></i> مشاركة الموقع
    </button>
</div>

<script>
    let previewTimer;

    function fetchPreview() {
        clearTimeout(previewTimer);
        const url = document.getElementById('media-url').value.trim();
        const previewBox = document.getElementById('preview-box');

        if (url.startsWith('http')) {
            previewTimer = setTimeout(() => {
                fetch('/api/preview?url=' + encodeURIComponent(url))
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            document.getElementById('preview-img').src = data.thumbnail;
                            document.getElementById('preview-title').innerText = data.title;
                            previewBox.style.display = 'block';
                        }
                    }).catch(() => {});
            }, 800);
        } else {
            previewBox.style.display = 'none';
        }
    }

    function startDownload() {
        const url = document.getElementById('media-url').value.trim();
        const fmt = document.getElementById('format-type').value;
        if (!url) { alert('الرجاء أدخال رابط صحيح أولاً!'); return; }

        const pBox = document.getElementById('progress-box');
        const pFill = document.getElementById('progress-fill');
        const pStatus = document.getElementById('progress-status');

        pBox.style.display = 'block';
        pFill.style.width = '30%';
        pStatus.innerText = 'جاري المعالجة والصنع...';

        fetch('/download', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url: url, format_type: fmt})
        })
        .then(response => {
            pFill.style.width = '80%';
            pStatus.innerText = 'جاري تجهيز الملف لتنزيله...';
            return response.blob();
        })
        .then(blob => {
            pFill.style.width = '100%';
            pStatus.innerText = 'تم التحميل بنجاح!';
            
            const link = document.createElement('a');
            link.href = window.URL.createObjectURL(blob);
            link.download = "downloaded_media";
            link.click();

            setTimeout(() => { pBox.style.display = 'none'; }, 2000);
            location.reload();
        })
        .catch(err => {
            alert('حدث خطأ أثناء التحميل.');
            pBox.style.display = 'none';
        });
    }

    function shareSite() {
        if (navigator.share) {
            navigator.share({ title: 'مُحمّل الميديا', url: window.location.href });
        } else {
            navigator.clipboard.writeText(window.location.href);
            alert('تم نسخ رابط الموقع للحافظة!');
        }
    }
</script>

</body>
</html>
"""

@app.route('/')
def home():
    stats = get_stats()
    return render_template_string(HTML_TEMPLATE, downloads=stats["downloads"])

@app.route('/api/preview')
def api_preview():
    url = request.args.get('url')
    try:
        info = get_media_info(url)
        return jsonify({'success': True, **info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/download', methods=['POST'])
def web_download():
    data = request.get_json()
    url = data.get('url')
    fmt = data.get('format_type', 'video_best')
    try:
        file_path = download_media(url, format_type=fmt)
        if isinstance(file_path, list):
            file_path = file_path[0]
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/admin')
def admin_panel():
    password = request.args.get('pass')
    if password == '123456':
        stats = get_stats()
        return f"<h1>لوحة التحكم الخاصة بك</h1><p>إجمالي التحميلات حتى الآن: <b>{stats['downloads']}</b></p>"
    return "خطأ: غير مصرح لك بدخول لوحة التحكم."
