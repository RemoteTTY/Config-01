# Daily/Weekly News Word Cloud (Paris + Trump)

This project gives you a **free-tier friendly** way to build a "word cloud of the day" (or week) from web news mentions of **Paris** and **Trump** using the Mediastack API.

## What it does

- Queries Mediastack for articles in a configurable time window (`day` or `week`)
- Searches for required keywords (defaults: `Paris,Trump`)
- Saves raw API results as JSON snapshots
- Cleans/tokenizes text and generates a PNG word cloud
- Logs top terms for quick review

> Note: free news APIs often return title + description, not full article bodies, so the cloud mostly reflects those fields.

## 1) Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` and set your key:

```bash
cp .env.example .env
# edit .env and set MEDIASTACK_API_KEY
```

Then export it:

```bash
set -a
source .env
set +a
```

## 2) Run manually

Daily window:

```bash
python news_wordcloud.py --api-key "$MEDIASTACK_API_KEY" --window day
```

Weekly window:

```bash
python news_wordcloud.py --api-key "$MEDIASTACK_API_KEY" --window week
```

Outputs go to `output/`:

- `*_mentions_YYYYMMDD_HHMMSS.json` (raw articles)
- `*_mentions_YYYYMMDD_HHMMSS.png` (word cloud image)

## 3) Customize query

Example for tariffs + Trump:

```bash
python news_wordcloud.py \
  --api-key "$MEDIASTACK_API_KEY" \
  --window day \
  --keywords "tariffs,Trump"
```

Extra stopwords:

```bash
python news_wordcloud.py \
  --api-key "$MEDIASTACK_API_KEY" \
  --extra-stopwords "will,just,people"
```

## 4) Automate daily with cron

Open crontab:

```bash
crontab -e
```

Run daily at 06:00 UTC:

```cron
0 6 * * * cd /workspace/Config-01 && /usr/bin/env bash -lc 'source .venv/bin/activate && set -a && source .env && set +a && python news_wordcloud.py --api-key "$MEDIASTACK_API_KEY" --window day >> logs/wordcloud.log 2>&1'
```

Before enabling cron, create logs dir:

```bash
mkdir -p logs
```

## 5) Avoiding blocks / reliability notes

- Use API-based collection (Mediastack) instead of direct scraping to reduce blocking risk.
- Keep request volume modest (`--max-pages`, `--limit`) to stay in free-tier limits.
- Script handles API/network failures with clear logs and non-zero exit status.
- If you need richer coverage, rotate multiple free sources or switch to a paid tier.

## 6) Optional enhancements

- Email notification on success/failure (SMTP)
- Store top terms in SQLite for trend charts
- Publish latest PNG to a simple static page
