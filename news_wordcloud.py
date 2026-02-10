#!/usr/bin/env python3
"""Generate daily/weekly word clouds from Mediastack news mentions."""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests
from wordcloud import WordCloud

MEDIASTACK_BASE_URL = "http://api.mediastack.com/v1/news"
DEFAULT_KEYWORDS = ["Paris", "Trump"]
DEFAULT_STOPWORDS = {
    "paris",
    "trump",
    "said",
    "says",
    "would",
    "could",
    "also",
    "one",
    "new",
    "news",
    "today",
    "week",
    "day",
    "according",
    "report",
    "reports",
    "reuters",
    "ap",
    "afp",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a word cloud from Mediastack mentions over a day or week."
    )
    parser.add_argument("--api-key", required=True, help="Mediastack API key")
    parser.add_argument(
        "--window",
        choices=["day", "week"],
        default="day",
        help="Lookback window for article search",
    )
    parser.add_argument(
        "--keywords",
        default=",".join(DEFAULT_KEYWORDS),
        help="Comma-separated required search terms (default: Paris,Trump)",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Article language filter supported by Mediastack (default: en)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum results per page (free tier supports up to 100)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Maximum pages to request (keeps usage under free-tier quota)",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for generated images and snapshots",
    )
    parser.add_argument(
        "--min-word-length",
        type=int,
        default=4,
        help="Minimum token length to include in cloud",
    )
    parser.add_argument(
        "--extra-stopwords",
        default="",
        help="Comma-separated extra stopwords",
    )
    return parser.parse_args()


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def get_date_window(mode: str) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    if mode == "day":
        start = now - timedelta(days=1)
    else:
        start = now - timedelta(days=7)
    return start.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")


def fetch_articles(
    api_key: str,
    keywords: Iterable[str],
    start_date: str,
    end_date: str,
    language: str,
    limit: int,
    max_pages: int,
) -> list[dict]:
    query = " AND ".join(keywords)
    all_articles: list[dict] = []
    offset = 0

    for page in range(max_pages):
        params = {
            "access_key": api_key,
            "keywords": query,
            "languages": language,
            "date": f"{start_date},{end_date}",
            "sort": "published_desc",
            "limit": limit,
            "offset": offset,
        }
        logging.info("Fetching page %s offset=%s", page + 1, offset)
        response = requests.get(MEDIASTACK_BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()

        if "error" in payload:
            error = payload["error"]
            raise RuntimeError(
                f"Mediastack error: {error.get('code')} - {error.get('message')}"
            )

        batch = payload.get("data", [])
        if not batch:
            break

        all_articles.extend(batch)
        offset += len(batch)

        if len(batch) < limit:
            break

    return all_articles


def save_snapshot(articles: list[dict], output_dir: Path, stem: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_dir / f"{stem}.json"
    snapshot_path.write_text(json.dumps(articles, indent=2), encoding="utf-8")
    return snapshot_path


def build_corpus(articles: list[dict]) -> str:
    parts: list[str] = []
    for article in articles:
        title = article.get("title") or ""
        description = article.get("description") or ""
        text = article.get("snippet") or article.get("content") or ""
        parts.extend([title, description, text])
    return "\n".join(parts)


def tokenize(text: str, min_word_length: int, stopwords: set[str]) -> Counter:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z'-]+", text.lower())
    filtered = [
        tok
        for tok in tokens
        if len(tok) >= min_word_length and tok not in stopwords and not tok.startswith("http")
    ]
    return Counter(filtered)


def create_wordcloud(freq: Counter, output_file: Path) -> None:
    if not freq:
        raise ValueError("No tokens available after filtering; try lowering min-word-length.")

    wc = WordCloud(
        width=1600,
        height=900,
        background_color="white",
        colormap="viridis",
        max_words=200,
    )
    wc.generate_from_frequencies(freq)
    wc.to_file(output_file)


def main() -> int:
    args = parse_args()
    setup_logging()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    stopwords = set(DEFAULT_STOPWORDS)
    stopwords.update({k.lower() for k in keywords})
    if args.extra_stopwords:
        stopwords.update(
            w.strip().lower() for w in args.extra_stopwords.split(",") if w.strip()
        )

    start_date, end_date = get_date_window(args.window)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stem = f"{args.window}_mentions_{timestamp}"
    output_dir = Path(args.output_dir)

    try:
        articles = fetch_articles(
            api_key=args.api_key,
            keywords=keywords,
            start_date=start_date,
            end_date=end_date,
            language=args.language,
            limit=args.limit,
            max_pages=args.max_pages,
        )
    except Exception:
        logging.exception("Failed to fetch articles")
        return 1

    if not articles:
        logging.warning("No articles returned for query: %s", keywords)
        return 0

    snapshot_path = save_snapshot(articles, output_dir, stem)
    corpus = build_corpus(articles)
    freq = tokenize(corpus, args.min_word_length, stopwords)

    image_path = output_dir / f"{stem}.png"
    try:
        create_wordcloud(freq, image_path)
    except Exception:
        logging.exception("Failed to generate word cloud")
        return 1

    top_terms = freq.most_common(20)
    logging.info("Saved raw article snapshot to %s", snapshot_path)
    logging.info("Saved word cloud image to %s", image_path)
    logging.info("Top terms: %s", top_terms)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
