import yt_dlp
import os

def download_media(url, progress_callback=None):
    def ytdlp_hook(d):
        if d['status'] == 'downloading' and progress_callback:
            # استخراج نسبة التحميل الحالية
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('_speed_str', 'N/A')
            
            if total > 0:
                percent = (downloaded / total) * 100
                progress_callback(percent, speed)

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [],
        'progress_hooks': [ytdlp_hook] if progress_callback else [],
    }
    
    os.makedirs('downloads', exist_ok=True)
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename
