import os
from datetime import datetime, time
import pytz
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_USER_ID = int(os.environ["TELEGRAM_USER_ID"])

IST = pytz.timezone("Asia/Kolkata")
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

REMINDER_HOUR = 22  # 10 PM IST


def today_str():
    return datetime.now(IST).strftime("%Y-%m-%d")


def format_time_label(dt):
    hour = dt.strftime("%I").lstrip("0") or "12"
    minute = dt.strftime("%M")
    ampm = dt.strftime("%p")
    return f"**{hour}:{minute} {ampm}**"


def log_file(date_str=None):
    return LOG_DIR / f"{date_str or today_str()}.md"


def ensure_header(f, now):
    if not f.exists():
        f.write_text(f"# {now.strftime('%B')} {now.day}, {now.year}\n\n")


def append_text_entry(text):
    now = datetime.now(IST)
    time_label = format_time_label(now)
    f = log_file()
    ensure_header(f, now)
    with f.open("a") as fp:
        fp.write(f"{time_label} — {text}\n")
    return time_label.replace("**", "")


def append_photo_entry(image_rel_path, caption=None):
    now = datetime.now(IST)
    time_label = format_time_label(now)
    f = log_file()
    ensure_header(f, now)

    with f.open("a") as fp:
        if caption:
            fp.write(f"{time_label} — {caption}\n\n")
        else:
            fp.write(f"{time_label}\n\n")
        fp.write(f"![]({image_rel_path})\n\n")

    return time_label.replace("**", "")


def get_today_log():
    f = log_file()
    if not f.exists():
        return None
    return f.read_text().strip()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    text = update.message.text.strip()
    if not text:
        return

    try:
        time_label = append_text_entry(text)
        await update.message.reply_text(f"logged at {time_label} IST")
    except Exception as e:
        await update.message.reply_text(f"error: {e}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    now = datetime.now(IST)
    caption = (update.message.caption or "").strip() or None
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H-%M-%S")

    # Save image to logs/images/YYYY-MM-DD/HH-MM-SS.jpg
    img_dir = LOG_DIR / "images" / date_str
    img_dir.mkdir(parents=True, exist_ok=True)
    img_path = img_dir / f"{time_str}.jpg"

    try:
        photo = update.message.photo[-1]  # highest resolution
        file = await context.bot.get_file(photo.file_id)
        await file.download_to_drive(img_path)

        # Relative path as it will appear in musings/YYYY-MM-DD.md
        image_rel_path = f"images/{date_str}/{time_str}.jpg"
        time_label = append_photo_entry(image_rel_path, caption)
        await update.message.reply_text(f"photo logged at {time_label} IST")
    except Exception as e:
        await update.message.reply_text(f"error: {e}")


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    await update.message.reply_text(
        "musings bot ready.\n\n"
        "• send text → logged with timestamp\n"
        "• send photo → saved to logs/images/date/\n"
        "• send photo with caption → image + text logged together\n\n"
        f"i'll remind you at {REMINDER_HOUR}:00 IST to push to your site."
    )


async def handle_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    content = get_today_log()
    if not content:
        await update.message.reply_text("nothing logged today.")
        return

    await update.message.reply_text(f"today's log:\n\n```\n{content}\n```", parse_mode="Markdown")


async def send_reminder(context):
    content = get_today_log()
    if not content:
        return

    date_str = today_str()
    msg = (
        f"end of day — copy this to `musings/{date_str}.md`\n"
        f"also copy `bot/logs/images/{date_str}/` → `musings/images/{date_str}/`\n\n"
        f"```\n{content}\n```"
    )
    await context.bot.send_message(
        chat_id=ALLOWED_USER_ID,
        text=msg,
        parse_mode="Markdown",
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("log", handle_log))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    reminder_time = time(hour=REMINDER_HOUR, minute=0, tzinfo=IST)
    app.job_queue.run_daily(send_reminder, time=reminder_time)

    print(f"bot started. daily reminder at {REMINDER_HOUR}:00 IST.")
    app.run_polling()


if __name__ == "__main__":
    main()
