import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 1. إعداد سجل التنبيهات والأخطاء (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 2. التوكن الخاص بالبوت
BOT_TOKEN = "8665209511:AAEJOET0jWMNb610jQyHfJepU-5Zgs7yU8Y"

# 3. أمر البداية (/start)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🎮 **مرحباً بك في بوت تغيير افتارات سوني (PSN Avatar Changer)** 🎮\n\n"
        "لتغيير الأفتار الخاص بحسابك، قم بطلب الأمر بالطريقة التالية:\n"
        "`/set_avatar <NPSSO_TOKEN> <AVATAR_ID>`\n\n"
        "💡 **مثال:**\n"
        "`/set_avatar YOUR_NPSSO_TOKEN CUSA00000_00`\n\n"
        "للحصول على المساعدة أرسل الأمر: /help"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

# 4. أمر المساعدة (/help)
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📌 **طريقة الاستخدام:**\n"
        "1. قم باستخراج رمز `NPSSO` من حسابك في موقع سوني الرسمي.\n"
        "2. احصل على رمز الأفتار المطلوب (`Avatar ID`).\n"
        "3. أرسل الأمر للبوت كالتالي:\n"
        "`/set_avatar <NPSSO> <AVATAR_ID>`"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# 5. دالة الاتصال بخوادم سوني لتعديل الأفتار
def change_psn_avatar(npsso_token: str, avatar_id: str) -> tuple[bool, str]:
    try:
        url = "https://m.np.playstation.com/api/userProfile/v1/users/me/avatar"
        
        headers = {
            "Authorization": f"Bearer {npsso_token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (PlayStation)"
        }
        
        payload = {
            "avatarId": avatar_id
        }
        
        response = requests.put(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            return True, "تم تغيير الأفتار بنجاح! 🎉"
        elif response.status_code == 401:
            return False, "رمز NPSSO / Access Token غير صالح أو انتهت صلاحيته."
        else:
            return False, f"فشلت العملية (رمز الخطأ من سوني: {response.status_code})."
            
    except Exception as e:
        return False, f"حدث خطأ أثناء الاتصال بالخادم: {str(e)}"

# 6. معالج أمر تغيير الأفتار (/set_avatar)
async def set_avatar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ **خطأ في الصيغة!**\n"
            "يرجى إدخال رمز NPSSO ومعرف الأفتار بالشكل الصحيح:\n"
            "`/set_avatar <NPSSO_TOKEN> <AVATAR_ID>`",
            parse_mode='Markdown'
        )
        return

    npsso_token = context.args[0]
    avatar_id = context.args[1]

    await update.message.reply_text("⏳ جاري معالجة الطلب والتواصل مع خوادم سوني...")

    success, message = change_psn_avatar(npsso_token, avatar_id)

    if success:
        await update.message.reply_text(f"✅ {message}")
    else:
        await update.message.reply_text(f"❌ {message}")

# 7. تشغيل البوت الرئيسي
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # تسجيل الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("set_avatar", set_avatar_handler))

    print("🚀 البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
