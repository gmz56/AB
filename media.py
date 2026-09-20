import os
import json
import requests
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

def fast_tiktok_download(url):
    """تحميل سريع جداً لمقاطع تيك توك عبر API مباشر"""
    try:
        api_url = f"https://api.tiklydown.eu.org/api/download?url={url}"
        res = requests.get(api_url, timeout=5).json()
        video_url = res.get('video', {}).get('noWatermark') or res.get('video', {}).get('watermark')
        if video_url:
            os.makedirs('downloads', exist_ok=True)
            filename = f"downloads/tiktok_{os.urandom(4).hex()}.mp4"
            v_res = requests.get(video_url, timeout=10)
            with open(filename, 'wb') as f:
                f.write(v_res.content)
            increment_stats()
            return filename
    except Exception as e:
        print(f"Fast TikTok Error: {e}")
    return None

def download_media(url, format_type="video_best"):
    # إذا كان الرابط تيك توك، جرب التحميل السريع أولاً
    if "tiktok.com" in url and format_type != "audio_only":
        fast_file = fast_tiktok_download(url)
        if fast_file:
            return fast_file

    increment_stats()
    output_template = 'downloads/%(id)s.%(ext)s'
    os.makedirs('downloads', exist_ok=True)

    ydl_opts = {
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'concurrent_fragment_downloads': 10, # زيادة سرعة التنزيل المتوازي
    }

    if format_type == "audio_only":
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    elif format_type == "video_low":
        ydl_opts['format'] = 'worst[ext=mp4]/worst'
    else:
        ydl_opts['format'] = 'best[ext=mp4]/best'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
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
    <title>مُحمّل الميديا السريع ⚡️</title>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        body { background: #0d1117; color: #fff; font-family: 'Tajawal', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }
        .card { background: #161b22; border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; padding: 30px; width: 100%; max-width: 450px; text-align: center; }
        input, select, button { width: 100%; padding: 14px; margin-top: 12px; border-radius: 10px; border: none; font-size: 1rem; }
        input { background: #0d1117; color: #fff; border: 1px solid #30363d; }
        button { background: linear-gradient(135deg, #00f2fe, #4facfe); color: #000; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
<div class="card">
    <h1>🚀 التحميل السريع جداً</h1>
    <p>أدخل الرابط واحصل على الملف فوراً</p>
    <input type="url" id="url" placeholder="أدخل الرابط هنا...">
    <select id="fmt">
        <option value="video_best">🎬 فيديو أعلى جودة</option>
        <option value="audio_only">🎵 صوت فقط (MP3)</option>
    </select>
    <button onclick="dl()">⚡️ تحميل فوراً</button>
</div>
<script>
function dl(){
    const u = document.getElementById('url').value;
    const f = document.getElementById('fmt').value;
    if(!u) return alert('ضع رابطاً!');
    fetch('/download', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url:u, format_type:f})})
    .then(r=>r.blob()).then(b=>{
        const a = document.createElement('a');
        a.href = URL.createObjectURL(b);
        a.download = "media";
        a.click();
    });
}
</script>
</body>
</html>
"""

@app.route('/')
def home():
    stats = get_stats()
    return render_template_string(HTML_TEMPLATE, downloads=stats["downloads"])

@app.route('/download', methods=['POST'])
def web_download():
    data = request.get_json()
    url = data.get('url')
    fmt = data.get('format_type', 'video_best')
    try:
        file_path = download_media(url, format_type=fmt)
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 400
