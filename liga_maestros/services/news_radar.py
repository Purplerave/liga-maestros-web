"""News radar: RSS feeds, relevance scoring, cache."""

import time
from datetime import datetime, timedelta
from urllib.parse import urlsplit

import requests
from defusedxml import ElementTree as ET

import config

from ..utils import (
    news_relevance_score,
    normalize_news_text,
    parse_rfc822_to_iso,
    safe_read_json,
    safe_write_json,
    sanitize_xml_payload,
    strip_html,
)


def _is_recent(item, now=None):
    now = now or datetime.now()
    try:
        published = datetime.strptime(item.get("published_at") or "", "%Y-%m-%d %H:%M")
        return now - timedelta(days=7) <= published <= now + timedelta(hours=6)
    except (TypeError, ValueError):
        return False


def fetch_feed_items(feed):
    feed_url = urlsplit(feed["url"])
    if feed_url.scheme not in {"http", "https"} or not feed_url.hostname:
        raise ValueError("Fuente RSS no permitida")
    response = requests.get(
        feed["url"],
        headers={
            "User-Agent": "Mozilla/5.0 LigaMaestrosRadar/1.0",
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        },
        timeout=12,
    )
    response.raise_for_status()
    payload = sanitize_xml_payload(response.content)
    root = ET.fromstring(payload)
    items = []
    for item in root.findall(".//item"):
        title = strip_html(item.findtext("title", ""))
        link = strip_html(item.findtext("link", ""))
        desc = strip_html(item.findtext("description", ""))
        pub = parse_rfc822_to_iso(item.findtext("pubDate", ""))
        joined = f"{title} {desc}".strip()
        score = news_relevance_score(joined)
        link_parts = urlsplit(link)
        if not title or link_parts.scheme not in {"http", "https"} or not link_parts.hostname:
            continue
        items.append(
            {
                "source": feed["name"],
                "source_id": feed["id"],
                "title": title,
                "link": link,
                "summary": desc[:220],
                "published_at": pub,
                "score": score,
            }
        )
    return items


def build_news_radar(force=False):
    cache = safe_read_json(config.NEWS_CACHE_PATH, {})
    now = time.time()
    fetched_at = float(cache.get("fetched_at_ts") or 0)
    if not force and cache and now - fetched_at < config.NEWS_REFRESH_SECONDS:
        cached = dict(cache)
        cached["items"] = [item for item in cache.get("items") or [] if _is_recent(item)]
        return cached

    merged = []
    errors = []
    for feed in config.NEWS_FEEDS:
        try:
            merged.extend(fetch_feed_items(feed))
        except Exception as exc:
            errors.append(f"{feed['name']}: {exc}")

    dedup = {}
    for item in merged:
        key = normalize_news_text(item["title"])
        prev = dedup.get(key)
        if not prev or item["score"] > prev["score"]:
            dedup[key] = item

    selected = [item for item in dedup.values() if item["score"] > 0 and _is_recent(item)]
    selected.sort(key=lambda x: (x["published_at"], x["score"]), reverse=True)
    selected = selected[:10]
    payload = {
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fetched_at_ts": now,
        "items": selected,
        "sources": [feed["name"] for feed in config.NEWS_FEEDS],
    }
    if force:
        payload["errors"] = errors[:5]
    safe_write_json(config.NEWS_CACHE_PATH, payload)
    if errors:
        payload["errors"] = errors[:5]
    return payload
