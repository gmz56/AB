import yt_dlp
import os

def download_media(url):
    ydl_opts = {
        # جلب أعلى جودة أصلية جاهزة MP4 مع الصوت الأصلي دون ضغط أو تعديل
        'format': 'best[ext=mp4]/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        # حظر أي عملية معالجة قد تؤثر على جودة الفيديو أو الصوت
        'postprocessors': [],
    }
    
    os.makedirs('downloads', exist_ok=True)
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename
