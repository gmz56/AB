import os
import json
import logging
import gc
import requests
import time
import base64
import yt_dlp
from io import BytesIO
from threading import Thread
from flask import Flask, render_template_string, request, jsonify, send_file
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, InlineQueryHandler, filters, ContextTypes

# التحقق من وجود مكتبة PIL لصناعة البطاقات
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
COUNTER_FILE = "stats.json"
USERS_FILE = "users.json"
REFERRALS_FILE = "referrals.json"

ADMIN_ID = os.getenv("ADMIN_ID")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# --- إدارة الإحصائيات والمستخدمين والإحالات ---
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

def save_user(user_id):
    users = set()
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                users = set(json.load(f))
        except:
            pass
    users.add(user_id)
    with open(USERS_FILE, 'w') as f:
        json.dump(list(users), f)

def get_referrals():
    if os.path.exists(REFERRALS_FILE):
        try:
            with open(REFERRALS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def add_referral(referrer_id, new_user_id):
    ref_data = get_referrals()
    referrer_str = str(referrer_id)
    new_user_str = str(new_user_id)
    
    if referrer_str != new_user_str:
        if referrer_str not in ref_data:
            ref_data[referrer_str] = []
        
        # التأكد من أن المستخدم الجديد لم يتم دعوته مسبقاً
        all_referred = [uid for sublist in ref_data.values() for uid in sublist]
        if new_user_str not in all_referred:
            ref_data[referrer_str].append(new_user_str)
            with open(REFERRALS_FILE, 'w') as f:
                json.dump(ref_data, f)
            return True
    return False

def get_user_ref_count(user_id):
    ref_data = get_referrals()
    return len(ref_data.get(str(user_id), []))

def clean_url(url):
    clean = url.split("?")[0].strip()
    if "tiktok.com" in clean and "/photo/" in clean:
        clean = clean.replace("/photo/", "/video/")
    return clean

# --- توليد بطاقات التهنئة باليوم الوطني 96 ---
def generate_national_card(name):
    width, height = 1080, 1080
    image = Image.new("RGB", (width, height), color=(0, 108, 53)) # الأخضر السعودي
    draw = ImageDraw.Draw(image)
    
    # رسم إطار ذهبي
    draw.rectangle([30, 30, width - 30, height - 30], outline=(212, 175, 55), width=10)
    draw.rectangle([50, 50, width - 50, height - 50], outline=(255, 255, 255), width=2)
    
    # نص التهنئة
    text_header = "🇸🇦 اليوم الوطني السعودي 96 🇸🇦"
    text_motto = "« عِــزّنَــا بِــطَــبْــعِــنَــا »"
    text_body = f"نهنئكم بمناسبة اليوم الوطني المجيد\nإهداء خاص إلى: {name}"
    
    draw.text((width // 2, 250), text_header, fill=(212, 175, 55), anchor="mm")
    draw.text((width // 2, 450), text_motto, fill=(255, 255, 255), anchor="mm")
    draw.text((width // 2, 650), text_body, fill=(212, 175, 55), anchor="mm")
    
    bio = BytesIO()
    bio.name = 'national_day_card.png'
    image.save(bio, 'PNG')
    bio.seek(0)
    return bio

# --- معالجة الذكاء الاصطناعي لمسح النصوص (AI Inpainting) ---
def process_ai_inpainting(video_path):
    if not REPLICATE_API_TOKEN:
        logger.warning("لم يتم العثور على REPLICATE_API_TOKEN، سيتم إرجاع الفيديو الأصلي.")
        return video_path

    try:
        headers = {
            "Authorization": f"Token {REPLICATE_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        with open(video_path, 'rb') as f:
            encoded_video = base64.b64encode(f.read()).decode('utf-8')
        
        upload_req = requests.post(
            "https://api.replicate.com/v1/models/sczhou/propainter/predictions",
            headers=headers,
            json={
                "input": {
                    "video": f"data:video/mp4;base64,{encoded_video}"
                }
            }
        )
        
        res_data = upload_req.json()
        prediction_id = res_data.get("id")
        
        if not prediction_id:
            logger.error(f"خطأ في Replicate: {res_data}")
            return video_path

        status_url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        for _ in range(60):
            time.sleep(2)
            check_res = requests.get(status_url, headers=headers).json()
            status = check_res.get("status")
            
            if status == "succeeded":
                output_url = check_res.get("output")
                if output_url:
                    clean_path = video_path.replace(".mp4", "_clean.mp4")
                    v_data = requests.get(output_url).content
                    with open(clean_path, 'wb') as out_f:
                        out_f.write(v_data)
                    if os.path.exists(video_path):
                        os.remove(video_path)
                    return clean_path
                break
            elif status in ["failed", "canceled"]:
                logger.error(f"فشلت عملية الذكاء الاصطناعي: {check_res}")
                break

    except Exception as e:
        logger.error(f"خطأ أثناء معالجة AI Inpainting: {e}")
    
    return video_path

# --- تحميل الميديا ---
def download_media(url, format_type="video_best", remove_text=False):
    increment_stats()
    os.makedirs('downloads', exist_ok=True)
    target_url = clean_url(url)
    
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'format': 'best',
        'max_filesize': 50 * 1024 * 1024,
    }

    if format_type == "audio_only":
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(target_url, download=True)
        filename = ydl.prepare_filename(info)
        
        if format_type == "audio_only":
            base, _ = os.path.splitext(filename)
            filename = base + ".mp3"
        elif remove_text and filename.endswith('.mp4'):
            filename = process_ai_inpainting(filename)
            
        return filename

# --- واجهة الويب المحميّة والاحتفالية (HTML / CSS) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🇸🇦 اليوم الوطني السعودي 96 | التحميل والمسح الذكي ⚡️</title>
    <style>
        :root {
            --saudi-green: #006c35;
            --saudi-gold: #d4af37;
            --dark-bg: #09130e;
            --card-bg: #112218;
            --text-light: #f4f4f4;
        }
        body { 
            background: var(--dark-bg); 
            color: var(--text-light); 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            display: flex; 
            flex-direction: column;
            justify-content: center; 
            align-items: center; 
            min-height: 100vh; 
            margin: 0; 
            padding: 20px;
            box-sizing: border-box;
        }
        .banner {
            background: linear-gradient(135deg, var(--saudi-green), #00381b);
            border: 2px solid var(--saudi-gold);
            border-radius: 12px;
            padding: 12px 20px;
            text-align: center;
            margin-bottom: 20px;
            width: 100%;
            max-width: 460px;
        }
        .banner h3 { margin: 0; color: var(--saudi-gold); font-size: 16px; }
        .banner p { margin: 4px 0 0 0; font-size: 13px; color: #fff; }
        
        .card { 
            background: var(--card-bg); 
            padding: 25px; 
            border-radius: 20px; 
            text-align: center; 
            width: 100%; 
            max-width: 460px; 
            box-shadow: 0 10px 30px #000; 
            border: 1px solid #d4af37; 
        }
        h2 { margin-bottom: 15px; color: var(--saudi-gold); font-size: 22px; }
        
        input[type="text"], input[type="url"] { 
            width: 100%; 
            padding: 14px; 
            margin-bottom: 15px; 
            border-radius: 10px; 
            border: 1px solid var(--saudi-green); 
            background: #06110a; 
            color: #fff; 
            box-sizing: border-box; 
            font-size: 14px; 
            text-align: center; 
        }
        .options { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; text-align: right; font-size: 14px; }
        .option-item { display: flex; align-items: center; gap: 10px; background: #0b1a11; padding: 12px; border-radius: 10px; cursor: pointer; border: 1px solid #183323; }
        
        .btn-green { 
            width: 100%; 
            padding: 14px; 
            border-radius: 10px; 
            border: none; 
            background: linear-gradient(135deg, var(--saudi-green), #00a852); 
            color: #fff; 
            font-weight: bold; 
            font-size: 16px; 
            cursor: pointer; 
            transition: 0.2s; 
        }
        .btn-green:hover { filter: brightness(1.1); }
        .btn-gold {
            background: linear-gradient(135deg, var(--saudi-gold), #aa8513);
            color: #000;
            margin-top: 10px;
        }

        .tab-buttons { display: flex; gap: 10px; margin-bottom: 20px; width: 100%; max-width: 460px; }
        .tab-btn { flex: 1; padding: 10px; background: #112218; border: 1px solid var(--saudi-green); color: #fff; border-radius: 10px; cursor: pointer; font-size: 13px; font-weight: bold; }
        .tab-btn.active { background: var(--saudi-green); border-color: var(--saudi-gold); }

        #cardCanvas { display: none; margin: 15px auto; max-width: 100%; border-radius: 12px; border: 2px solid var(--saudi-gold); }
        #status { margin-top: 15px; font-size: 13px; color: #a0b0a5; }

        .footer-rights {
            margin-top: 25px;
            width: 100%;
            max-width: 460px;
            text-align: center;
            font-size: 12px;
            color: #7b9384;
            border-top: 1px solid #183323;
            padding-top: 15px;
        }
        .footer-rights b { color: var(--saudi-gold); }
        .disclaimer {
            background: #08120b;
            padding: 10px;
            border-radius: 8px;
            margin-top: 10px;
            font-size: 11px;
            line-height: 1.5;
            color: #8fa397;
            text-align: justify;
        }
    </style>
</head>
<body>

<div class="banner">
    <h3>🇸🇦 اليوم الوطني السعودي 96 | عزّنا بطبعنا 🇸🇦</h3>
    <p>⚡️ أداة تحصيل الميديا والمسح الذكي المجانية 100%</p>
</div>

<div class="tab-buttons">
    <button class="tab-btn active" onclick="switchTab('downloader')">🚀 التحميل والمسح</button>
    <button class="tab-btn" onclick="switchTab('cardGen')">🎨 صانع بطاقات 96</button>
</div>

<div class="card" id="tab-downloader">
    <h2>⚡️ تحميل الميديا والمسح الذكي</h2>
    <input type="url" id="url" placeholder="ضع رابط الفيديو هنا...">
    
    <div class="options">
        <label class="option-item">
            <input type="radio" name="fmt" value="video_best" checked>
            <span>🎬 تحميل أصلي (بدون حقوق تيك توك)</span>
        </label>
        <label class="option-item">
            <input type="radio" name="fmt" value="video_ai">
            <span>🤖 مسح كامل للنصوص المدمجة (AI Inpainting)</span>
        </label>
        <label class="option-item">
            <input type="radio" name="fmt" value="audio_only">
            <span>🎵 تحميل الصوت فقط (MP3)</span>
        </label>
    </div>

    <button class="btn-green" onclick="dl()">بدء التحميل مجاناً ⚡️</button>
    <div id="status"></div>
</div>

<div class="card" id="tab-cardGen" style="display: none;">
    <h2>🎨 بطاقة تهنئة باليوم الوطني 96</h2>
    <input type="text" id="cardName" placeholder="اكتب اسمك هنا">
    <button class="btn-green btn-gold" onclick="createCard()">إنشاء البطاقة الفخمة ✨</button>
    
    <canvas id="cardCanvas" width="800" height="800"></canvas>
    <a id="downloadCardBtn" style="display:none;" class="btn-green" download="Saudi_96_Card.png">📥 تحميل البطاقة مجاناً</a>
</div>

<div class="footer-rights">
    <p>جميع الحقوق محفوظة وتعود لمطور الخدمة الأصلي © 2026 🇸🇦</p>
    <div class="disclaimer">
        ⚠️ <b>إخلاء مسؤولية وشروط الاستخدام:</b><br>
        هذا الموقع والبوت أداة تقنية مخصصة للاستخدام الشخصي والتعديل على المحتوى الخاص بك. لا يتم تخزين أو استضافة أي ملفات فيديو أو صوت على خوادمنا نهائياً. المستخدم يتحمل كامل المسؤولية القانونية والأخلاقية.
    </div>
</div>

<script>
function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    if(tab === 'downloader') {
        document.getElementById('tab-downloader').style.display = 'block';
        document.getElementById('tab-cardGen').style.display = 'none';
        event.target.classList.add('active');
    } else {
        document.getElementById('tab-downloader').style.display = 'none';
        document.getElementById('tab-cardGen').style.display = 'block';
        event.target.classList.add('active');
    }
}

function dl(){
    const u = document.getElementById('url').value;
    const statusDiv = document.getElementById('status');
    if(!u) return alert('يرجى إدخال رابط صحيح!');
    
    const selectedOption = document.querySelector('input[name="fmt"]:checked').value;
    let formatType = 'video_best';
    let removeText = false;

    if(selectedOption === 'video_ai') {
        formatType = 'video_best';
        removeText = true;
        statusDiv.innerText = "🤖 جاري معالجة الفيديو بالذكاء الاصطناعي ومسح النصوص...";
    } else if(selectedOption === 'audio_only') {
        formatType = 'audio_only';
        statusDiv.innerText = "⏳ جاري استخراج الصوت...";
    } else {
        statusDiv.innerText = "⏳ جاري التحميل المباشر...";
    }

    fetch('/download', {
        method: 'POST', 
        headers: {'Content-Type': 'application/json'}, 
        body: JSON.stringify({url: u, format_type: formatType, remove_text: removeText})
    })
    .then(r => {
        if(!r.ok) throw new Error("تعذر معالجة الرابط");
        return r.blob();
    })
    .then(b => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(b);
        a.download = (formatType === 'audio_only') ? "audio.mp3" : "video.mp4";
        a.click();
        statusDiv.innerText = "✅ تم التحميل بنجاح!";
    })
    .catch(err => {
        statusDiv.innerText = "❌ حدث خطأ، يرجى التأكد من الرابط والمحاولة مجدداً.";
    });
}

function createCard() {
    const name = document.getElementById('cardName').value || "محب الوطن";
    const canvas = document.getElementById('cardCanvas');
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = "#005228";
    ctx.fillRect(0, 0, 800, 800);

    ctx.strokeStyle = "#d4af37";
    ctx.lineWidth = 12;
    ctx.strokeRect(30, 30, 740, 740);

    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.strokeRect(45, 45, 710, 710);

    ctx.fillStyle = "#d4af37";
    ctx.font = "bold 40px 'Segoe UI', Tahoma";
    ctx.textAlign = "center";
    ctx.fillText("🇸🇦 اليوم الوطني السعودي 96 🇸🇦", 400, 180);

    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 55px 'Segoe UI', Tahoma";
    ctx.fillText("« عِــزّنَــا بِــطَــبْــعِــنَــا »", 400, 320);

    ctx.fillStyle = "#d4af37";
    ctx.font = "28px 'Segoe UI', Tahoma";
    ctx.fillText("تهنئة خاصة بمناسبة اليوم الوطني المجيد", 400, 480);

    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 38px 'Segoe UI', Tahoma";
    ctx.fillText(name, 400, 560);

    canvas.style.display = 'block';
    const btn = document.getElementById('downloadCardBtn');
    btn.href = canvas.toDataURL('image/png');
    btn.style.display = 'block';
}
</script>
</body>
</html>
"""

# --- مسارات Flask ---
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/download', methods=['POST'])
def web_download():
    data = request.get_json()
    file_path = None
    try:
        url = data.get('url')
        fmt = data.get('format_type', 'video_best')
        remove_txt = data.get('remove_text', False)
        
        file_path = download_media(url, format_type=fmt, remove_text=remove_txt)
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        logger.error(f"Web Download Error: {e}")
        return jsonify({'error': str(e)}), 400
    finally:
        if file_path and os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        gc.collect()

def run_flask_site():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# --- أوامر وتفاعلات بوت تليجرام ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    # معالجة رابط الدعوة والإحالة عند الدخول
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            try:
                referrer_id = int(arg.replace("ref_", ""))
                if add_referral(referrer_id, user_id):
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 **انضم مستخدم جديد عبر رابطك!**\nإجمالي أصدقائك المدعوين حتى الآن: **{get_user_ref_count(referrer_id)}** 🚀",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"فشل إرسال إشعار الإحالة: {e}")
            except ValueError:
                pass

    ref_count = get_user_ref_count(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🚀 زيارة موقع التحميل والمسح الذكي", url="https://ab-rbx9.onrender.com")],
        [InlineKeyboardButton("🎨 إنشاء بطاقة تهنئة باليوم الوطني", callback_data="make_card")],
        [InlineKeyboardButton(f"🎁 رابط الدعوة الخاص بك ({ref_count} مدعوين)", callback_data="my_ref")],
        [InlineKeyboardButton("📜 شروط الاستخدام وإخلاء المسؤولية", callback_data="terms")],
        [InlineKeyboardButton("🟢 مشاركة البوت مع الأصدقاء", callback_data="share_bot")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "🇸🇦 **كل عام والوطن بألف خير | اليوم الوطني السعودي 96** 🇸🇦\n\n"
        "أهلاً بك في بوت وموقع التحميل والمسح الذكي المجاني! ⚡️\n\n"
        "• أرسل رابط الفيديو للتحميل المباشر خالي من الحقوق.\n"
        "• أو استخدم الموقع لمسح الكتابة والنصوص بالذكاء الاصطناعي مجاناً! 💚\n\n"
        "🛡 _حقوق البرمجة والتطوير محفوظة لمطور الخدمة ©_"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "make_card":
        await query.message.reply_text("لإنشاء بطاقة تهنئة باسمك مجاناً، اكتب الأمر كالتالي:\n\n`/card اسمك`\nمثال: `/card مناع`", parse_mode="Markdown")
    elif query.data == "my_ref":
        ref_count = get_user_ref_count(user_id)
        bot_username = context.bot.username or "amxnfj37BOT"
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        
        ref_msg = (
            f"🎁 **رابط الإحالة والدعوة الخاص بك:**\n\n"
            f"`{ref_link}`\n\n"
            f"📊 عدد الأصدقاء الذين دخلوا عبر رابطك: **{ref_count}**\n\n"
            f"انشر الرابط في الجروبات ومع أصدقائك لزيادة انتشاره ودعم البوت! 🚀"
        )
        await query.message.reply_text(ref_msg, parse_mode="Markdown")
    elif query.data == "terms":
        terms_text = (
            "⚖️ **شروط الاستخدام وإخلاء المسؤولية القانونية:**\n\n"
            "1. هذا البوت والموقع أداة تقنية مخصصة للاستخدام الشخصي المشروع والتعديل على المحتوى الخاص بك.\n"
            "2. لا يتم استضافة أو حفظ أي فيديوهات/صوتيات على خوادمنا إطلاقاً، وتُحذف تلقائياً فور إرسالها.\n"
            "3. المستخدم يتحمل المسؤولية القانونية الكاملة عن أي استخدام غير مشروع أو انتهاك لحقوق الملكية الفكرية.\n"
            "4. جميع حقوق برمجة وتطوير البوت والموقع محفوظة لمطور الخدمة الأصلي ©."
        )
        await query.message.reply_text(terms_text, parse_mode="Markdown")
    elif query.data == "share_bot":
        share_url = f"https://t.me/share/url?url=https://t.me/{context.bot.username}&text=جرّب%20بوت%20التحميل%20ومسح%20النصوص%20بالذكاء%20الاصطناعي%20المجاني%20بمناسبة%20اليوم%20الوطني%2096%20🇸🇦"
        kb = [[InlineKeyboardButton("📲 إرسال إلى الواتساب / تليجرام", url=share_url)]]
        await query.message.reply_text("انشر البوت لأصدقائك مجاناً واحتفلوا باليوم الوطني! 💚", reply_markup=InlineKeyboardMarkup(kb))

# --- النمط المباشر (Inline Mode) ---
async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.inline_query.query.strip()
    bot_username = context.bot.username or "amxnfj37BOT"
    results = []

    if not query_text:
        results.append(
            InlineQueryResultArticle(
                id="1",
                title="⚡️ مشاركة بوت التحميل والمسح الذكي",
                description="اضغط هنا لإرسال رابط البوت لأصدقائك في هذه المحادثة",
                input_message_content=InputTextMessageContent(
                    f"🇸🇦 **بوت سلنقح للتحميل والمسح الذكي ⚡️**\n\n"
                    f"حمل مقاطع تيك توك بدون حقوق ونظف الفيديوهات بالذكاء الاصطناعي مجاناً!\n\n"
                    f"رابط البوت: https://t.me/{bot_username}",
                    parse_mode="Markdown"
                )
            )
        )
    else:
        results.append(
            InlineQueryResultArticle(
                id="2",
                title="🎬 رابط جاهز للمعالجة",
                description=f"إرسال الرابط للبوت: {query_text[:30]}...",
                input_message_content=InputTextMessageContent(
                    f"⚡️ **رابط للتحميل والتنظيف:**\n{query_text}\n\n"
                    f"اضغط على البوت لتنظيف المقاطع والتحميل مجاناً: @{bot_username}",
                    parse_mode="Markdown"
                )
            )
        )

    await update.inline_query.answer(results, cache_time=1)

async def card_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = " ".join(context.args) if context.args else update.effective_user.first_name
    
    if HAS_PIL:
        msg = await update.message.reply_text("⏳ جاري تصميم بطاقتك...")
        try:
            card_img = generate_national_card(name)
            await update.message.reply_photo(photo=card_img, caption=f"🇸🇦 بطاقة تهنئة باليوم الوطني 96 إهداء لـ **{name}** ✨\n\n_حقوق التطوير محفوظة لمطور الخدمة ©_", parse_mode="Markdown")
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"🇸🇦 **اليوم الوطني السعودي 96 | عزّنا بطبعنا**\n\nنهنئكم بمناسبة اليوم الوطني المجيد!\nإهداء خاص إلى: **{name}** 💚")
    else:
        await update.message.reply_text(f"🇸🇦 **اليوم الوطني السعودي 96 | عزّنا بطبعنا**\n\nنهنئكم بمناسبة اليوم الوطني المجيد!\nإهداء خاص إلى: **{name}** 💚", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    url = update.message.text
    if not url.startswith("http"):
        return
    
    msg = await update.message.reply_text("⏳ جاري التحميل المباشر...")
    try:
        file_path = download_media(url, format_type="video_best")
        with open(file_path, 'rb') as video:
            await update.message.reply_video(video=video, caption="تم التحميل بنجاح ⚡️\n🇸🇦 دام عزك يا وطن 🇸🇦\n\n_حقوق البوت والموقع محفوظة للمطور ©_")
        await msg.delete()
        os.remove(file_path)
    except Exception as e:
        await msg.edit_text("❌ تعذر تحميل المقطع.")

def main():
    Thread(target=run_flask_site, daemon=True).start()
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN: raise ValueError("TELEGRAM_BOT_TOKEN غير متوفر!")
    
    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("card", card_command))
    bot_app.add_handler(CallbackQueryHandler(button_click))
    bot_app.add_handler(InlineQueryHandler(inline_query_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    bot_app.run_polling()

if __name__ == "__main__":
    main()
