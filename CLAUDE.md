# Portfolio

A static personal portfolio site with a Telegram bot that powers a daily musings journal.

## Structure

```
portfolio/
├── index.html          # Home page
├── musings.html        # Musings journal page
├── contact.html
├── hobbies.html
├── inventions.html
├── life.html
├── skills.html
├── styles.css          # Single shared stylesheet
├── musings/
│   ├── index.json      # Ordered list of published musing files (newest first)
│   ├── YYYY-MM-DD.md   # One file per day
│   └── images/
│       └── YYYY-MM-DD/ # Images referenced by that day's markdown
├── bot/
│   ├── telegram_bot.py # Telegram bot that powers the journal
│   └── logs/
│       ├── YYYY-MM-DD.md     # Raw daily logs (source of truth)
│       └── images/           # Legacy image location (pre-bot-update)
└── scripts/
```

## Musings workflow

The bot logs text and photos sent via Telegram into `bot/logs/YYYY-MM-DD.md`.

- **Photos** are saved directly to `musings/images/YYYY-MM-DD/HH-MM-SS.jpg` (post-bot-update). Images saved before the bot update live in `bot/logs/images/` and must be copied manually.
- **Publishing** a day: send `/publish` (or `/publish YYYY-MM-DD`) from Telegram. This copies the log to `musings/` and adds it to `index.json`.
- **index.json** must be kept in reverse-chronological order.
- **April 13** is intentionally excluded from musings.

## Musings page (musings.html)

- Fetches `musings/index.json`, then loads each `.md` file and renders it with `marked.js`.
- Groups entries by month in both the TOC and content.
- Image paths in markdown are written as `images/YYYY-MM-DD/HH-MM-SS.jpg` (relative). The page JS rewrites these to `musings/images/...` at render time.
- `strong` elements are `display: block` so timestamps (the only bold text) always start on a new line.

## Bot commands

| Command | Effect |
|---|---|
| `/publish [YYYY-MM-DD]` | Copy log → musings, update index.json |
| `/log` | Show today's log |
| `/backfill YYYY-MM-DD` | Switch logging to a past date |
| `/today` | Return to logging today |

## Styles

All pages share `styles.css`. No build step — everything is plain HTML/CSS/JS.
