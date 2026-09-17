import os
import time
from media import download_media

async def handle_url(update, context):
    url = update.message.text
    status_msg = await update.message.reply_text("⏳ جاري البدء في التحميل...")
    
    last_update_time = [0]
    
    # دالة تحديث شريط التقدم في تيليجرام
    def progress_callback(percent, speed):
        current_time = time.time()
        # تحديث الرسالة كل 3 ثوانٍ فقط لتجنب حظر تيليجرام (Rate Limit)
        if current_time - last_update_time[0] > 3:
            last_update_time[0] = current_time
            text = f"⏳ جاري التحميل: {percent:.1f}%\n🚀 السرعة: {speed}"
            context.application.create_task(
                status_msg.edit_text(text)
            )

    file_path = None
    try:
        # 1. التنزيل
        file_path = download_media(url, progress_callback)
        await status_msg.edit_text("📤 جاري رفع الفيديو إليك...")
        
        # 2. الإرسال
        with open(file_path, 'rb') as video:
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=video,
                supports_streaming=True
            )
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ حدث خطأ أثناء التحميل: {e}")

    finally:
        # 3. التنظيف التلقائي للملف فور الانتهاء أو عند حدوث خطأ
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            print(f"🧹 تم حذف الملف المؤقت: {file_path}")
