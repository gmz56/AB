import os
import time
import logging
from threading import Thread
from flask import Flask, render_template_string, request, send_file, jsonify, after_this_request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from media import download_media

web_app = Flask(__name__)

HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مُحمّل الفيديوهات السريع</title>
    <style>
        * { box-sizing: border-box; font-family: system-ui, -apple-system, sans-serif; }
        body { background: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }
        .card { background: #1e293b; padding: 30px; border-radius: 16px; width: 100%; max-width: 500px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); text-align: center; }
        h1 { margin-bottom: 24px; font-size: 24px; color: #38bdf8; }
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
        <h1>🚀 مُحمّل الفيديوهات</h1>
        <input type="text" id="videoUrl" placeholder="أدخل رابط الفيديو (تيك توك، يوتيوب، إنستغرام...)" />
        <button id="downloadBtn" onclick="startDownload()">تحميل الفيديو</button>
        <div id="status"></div>
    </div>

    <script>
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
            status.innerText = "⏳ جاري جلب الفيديو وتجهيزه...";

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
                a.download = "video.mp4";
                document.body.appendChild(a);
                a.click();
                a.remove();
                status.innerText = "🎉 تم التحميل بنجاح!";
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

@web_app.route('/')
def home():
    return render_template_string(HTML_LAYOUT)

@web_app.route('/api/download', methods=['POST'])
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
                    logging.info(f"🧹 تم مسح الملف المؤقت للويب: {file_path}")
            except Exception as e:
                logging.error(f"خطأ في حذف ملف الويب: {e}")
            return response

        return send_file(file_path, as_attachment=True)

    except Exception as e:
        logging.error(f"Web Download Error: {e}")
        return jsonify({"error": str(e)}), 500

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! أرسل لي أي رابط فيديو وسأقوم بتحميله لك 🚀")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("الرجاء إرسال رابط صحيح يبتدئ بـ http أو https 🔗")
        return

    status_msg = await update.message.reply_text("⏳ جاري التحميل...")
    last_update_time = [0]

    def progress_callback(percent, speed):
        current_time = time.time()
        if current_time - last_update_time[0] > 3.5:
            last_update_time[0] = current_time
            bar_length = 10
            filled_length = int(bar_length * percent // 100)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            text = f"⏳ **جاري التحميل...**\n\n[{bar}] {percent:.1f}%\n🚀 **السرعة:** {speed}"
            try:
                context.application.create_task(status_msg.edit_text(text, parse_mode='Markdown'))
            except Exception:
                pass

    file_path = None
    try:
        file_path = download_media(url, progress_callback)
        await status_msg.edit_text("📤 جاري رفع الفيديو إليك...")
        with open(file_path, 'rb') as video_file:
            await context.bot.send_video(chat_id=update.effective_chat.id, video=video_file, supports_streaming=True)
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Telegram Download Error: {e}")
        await status_msg.edit_text(f"❌ حدث خطأ: {e}")
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as cleanup_err:
                logger.error(f"فشل حذف ملف تليجرام: {cleanup_err}")

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN غير متوفر!")

    Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
