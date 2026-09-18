import os
import uuid
import yt_dlp

def download_media(url, progress_callback=None):
    unique_id = str(uuid.uuid4())[:8]
    output_template = f"downloads/{unique_id}_%(title)s.%(ext)s"

    def my_hook(d):
        if d['status'] == 'downloading' and progress_callback:
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            if total_bytes and total_bytes > 0:
                percent = (downloaded / total_bytes) * 100
                speed = d.get('_speed_str', 'N/A')
                progress_callback(percent, speed)

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_template,
        'progress_hooks': [my_hook] if progress_callback else [],
        'quiet': True,
        'no_warnings': True,
        'cookiefile': 'cookies.txt',
    }

    os.makedirs('downloads', exist_ok=True)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename
