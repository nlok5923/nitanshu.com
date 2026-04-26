import json
import os
import shutil
import subprocess
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

MUSINGS_DIR = Path(__file__).parent.parent / "musings"
MUSINGS_IMG_DIR = MUSINGS_DIR / "images"
MUSINGS_IMG_DIR.mkdir(parents=True, exist_ok=True)

REMINDER_HOUR = 22  # 10 PM IST

# In-memory state: None means "today", a date string means backfill mode
active_date: str | None = None


def today_str():
    return datetime.now(IST).strftime("%Y-%m-%d")


def current_date():
    return active_date or today_str()


def format_time_label(dt):
    hour = dt.strftime("%I").lstrip("0") or "12"
    minute = dt.strftime("%M")
    ampm = dt.strftime("%p")
    return f"**{hour}:{minute} {ampm}**"


def log_file(date_str):
    return LOG_DIR / f"{date_str}.md"


def ensure_header(f, date_str):
    if not f.exists():
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            header = f"# {dt.strftime('%B')} {dt.day}, {dt.year}\n\n"
        except ValueError:
            header = f"# {date_str}\n\n"
        f.write_text(header)


def append_text_entry(text, date_str):
    now = datetime.now(IST)
    time_label = format_time_label(now)
    f = log_file(date_str)
    ensure_header(f, date_str)
    with f.open("a") as fp:
        fp.write(f"{time_label} — {text}\n")
    return time_label.replace("**", "")


def append_photo_entry(image_rel_path, date_str, caption=None):
    now = datetime.now(IST)
    time_label = format_time_label(now)
    f = log_file(date_str)
    ensure_header(f, date_str)
    with f.open("a") as fp:
        if caption:
            fp.write(f"{time_label} — {caption}\n\n")
        else:
            fp.write(f"{time_label}\n\n")
        fp.write(f"![]({image_rel_path})\n\n")
    return time_label.replace("**", "")


def git(args, cwd):
    result = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def publish_log(date_str):
    src = log_file(date_str)
    if not src.exists():
        return False, "no log found for that date."

    repo = MUSINGS_DIR.parent

    shutil.copy2(src, MUSINGS_DIR / f"{date_str}.md")

    index_file = MUSINGS_DIR / "index.json"
    entries = json.loads(index_file.read_text()) if index_file.exists() else []
    filename = f"{date_str}.md"
    if filename not in entries:
        entries.append(filename)
        entries.sort(reverse=True)
        index_file.write_text(json.dumps(entries) + "\n")

    img_dir = MUSINGS_IMG_DIR / date_str
    to_add = [
        f"musings/{date_str}.md",
        "musings/index.json",
    ]
    if img_dir.exists():
        to_add.append(f"musings/images/{date_str}/")

    git(["add"] + to_add, cwd=repo)
    git(["commit", "-m", f"publish {date_str} musings"], cwd=repo)
    git(["push"], cwd=repo)

    return True, f"published {date_str} and pushed to prod."


def get_log(date_str):
    f = log_file(date_str)
    if not f.exists():
        return None
    return f.read_text().strip()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    text = update.message.text.strip()
    if not text:
        return

    date_str = current_date()
    try:
        time_label = append_text_entry(text, date_str)
        suffix = f" (backfilling {date_str})" if active_date else ""
        await update.message.reply_text(f"logged at {time_label} IST{suffix}")
    except Exception as e:
        await update.message.reply_text(f"error: {e}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    now = datetime.now(IST)
    caption = (update.message.caption or "").strip() or None
    date_str = current_date()
    time_str = now.strftime("%H-%M-%S")

    img_dir = MUSINGS_IMG_DIR / date_str
    img_dir.mkdir(parents=True, exist_ok=True)
    img_path = img_dir / f"{time_str}.jpg"

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        await file.download_to_drive(img_path)

        image_rel_path = f"images/{date_str}/{time_str}.jpg"
        time_label = append_photo_entry(image_rel_path, date_str, caption)
        suffix = f" (backfilling {date_str})" if active_date else ""
        await update.message.reply_text(f"photo logged at {time_label} IST{suffix}")
    except Exception as e:
        await update.message.reply_text(f"error: {e}")


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    await update.message.reply_text(
        "musings bot ready.\n\n"
        "• send text → logged with timestamp\n"
        "• send photo (+ optional caption) → image + text logged together\n"
        "• /log → see today's log\n"
        "• /publish [YYYY-MM-DD] → push log to musings site\n"
        "• /backfill YYYY-MM-DD → switch to a past date\n"
        "• /today → back to logging today\n\n"
        f"daily reminder at {REMINDER_HOUR}:00 IST."
    )


async def handle_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    date_str = current_date()
    content = get_log(date_str)
    if not content:
        await update.message.reply_text(f"nothing logged for {date_str}.")
        return

    await update.message.reply_text(
        f"log for {date_str}:\n\n```\n{content}\n```",
        parse_mode="Markdown",
    )


async def handle_backfill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_date
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    args = context.args
    if not args:
        await update.message.reply_text("usage: /backfill YYYY-MM-DD")
        return

    date_str = args[0].strip()
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("invalid date. use YYYY-MM-DD format.")
        return

    active_date = date_str
    existing = get_log(date_str)
    status = "existing log found — new entries will be appended." if existing else "no log yet — will create one."
    await update.message.reply_text(
        f"backfill mode: logging to {date_str}\n{status}\n\nsend /today to go back to today."
    )


async def handle_publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    date_str = (context.args[0].strip() if context.args else None) or today_str()
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("invalid date. use YYYY-MM-DD format.")
        return

    try:
        ok, msg = publish_log(date_str)
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"error: {e}")


async def handle_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_date
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    active_date = None
    await update.message.reply_text(f"back to today ({today_str()}).")


async def send_reminder(context):
    content = get_log(today_str())
    if not content:
        return

    date_str = today_str()
    msg = (
        f"end of day — send /publish to push to the site\n"
        f"(images already saved to `musings/images/{date_str}/`)\n\n"
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
    app.add_handler(CommandHandler("publish", handle_publish))
    app.add_handler(CommandHandler("backfill", handle_backfill))
    app.add_handler(CommandHandler("today", handle_today))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    reminder_time = time(hour=REMINDER_HOUR, minute=0, tzinfo=IST)
    app.job_queue.run_daily(send_reminder, time=reminder_time)

    print(f"bot started. daily reminder at {REMINDER_HOUR}:00 IST.")
    app.run_polling()


if __name__ == "__main__":
    main()
