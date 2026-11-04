"""Benzinga News API client used to find a one-sentence catalyst per ticker.

Docs: https://docs.benzinga.com/benzinga-apis/newsfeed-v2/get-news
Requires an API key in BENZINGA_API_KEY.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import date, timedelta

import requests

log = logging.getLogger(__name__)

NEWS_URL = "https://api.benzinga.com/api/v2/news"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
# Sentence boundary: . ! ? followed by whitespace and a capital/quote/digit.
_BOUNDARY_RE = re.compile(r"[.!?]\s+(?=[A-Z\"'\d])")
# Abbreviations that end in a period but don't end a sentence.
_ABBREVIATIONS = {"inc", "corp", "co", "ltd", "plc", "vs", "u.s", "mr", "ms", "dr", "st", "no", "jan", "feb",
                  "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec"}


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", text))).strip()


def one_sentence(text: str | None, max_len: int = 220) -> str:
    """Reduce a headline/teaser to a single sentence ending in punctuation."""
    text = clean_text(text)
    if not text:
        return ""
    sentence = text
    for m in _BOUNDARY_RE.finditer(text):
        last_word = text[: m.start()].rsplit(" ", 1)[-1].lower()
        if last_word in _ABBREVIATIONS or len(last_word) == 1:  # "Inc." / initials like "J."
            continue
        sentence = text[: m.start() + 1]
        break
    sentence = sentence.strip()
    if len(sentence) > max_len:
        sentence = sentence[: max_len - 1].rsplit(" ", 1)[0].rstrip(",;:-") + "…"
    if sentence[-1] not in ".!?…":
        sentence += "."
    return sentence


class BenzingaClient:
    def __init__(self, api_key: str, timeout: float = 15.0, session: requests.Session | None = None):
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or requests.Session()

    def latest_news(self, ticker: str, lookback_days: int = 3, today: date | None = None) -> list[dict]:
        today = today or date.today()
        params = {
            "token": self.api_key,
            "tickers": ticker,
            "pageSize": 5,
            "displayOutput": "abstract",
            "sort": "created:desc",
            "dateFrom": (today - timedelta(days=lookback_days)).isoformat(),
        }
        resp = self.session.get(NEWS_URL, params=params, headers={"Accept": "application/json"}, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def catalyst(self, ticker: str, lookback_days: int = 3, today: date | None = None) -> dict | None:
        """Return {"sentence", "headline", "url", "published"} for the newest story, or None."""
        try:
            stories = self.latest_news(ticker, lookback_days, today)
        except (requests.RequestException, ValueError) as exc:
            log.warning("Benzinga request failed for %s: %s", ticker, exc)
            return None
        for story in stories:
            headline = clean_text(story.get("title"))
            sentence = one_sentence(headline or story.get("teaser"))
            if sentence:
                return {
                    "sentence": sentence,
                    "headline": headline,
                    "url": story.get("url"),
                    "published": story.get("created"),
                }
        return None
