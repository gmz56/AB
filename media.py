import yt_dlp
import os

def download_media(url):
    ydl_opts = {
        # جلب أعلى جودة ممتازة متوفرة بصيغة mp4 جاهزة دون معالجة المعالج
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    
    # إنشاء مجلد التنزيلات إذا لم يكن موجوداً
    os.makedirs('downloads', exist_ok=True)
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename
