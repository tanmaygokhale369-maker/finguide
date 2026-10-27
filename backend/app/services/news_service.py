"""Fetch short, source-linked official financial headlines and local sentiment.

The feed allowlist is deliberately fixed to publisher-operated RBI and SEBI
RSS endpoints. Article bodies are not fetched or persisted. Retrieved text is
untrusted data and never enters a prompt or recommendation policy.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html.parser import HTMLParser
import logging
import re
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from app.ai.news import get_sentiment_analyzer

logger = logging.getLogger(__name__)
MAX_FEED_BYTES = 512_000
MAX_ITEMS_PER_FEED = 30
MAX_ARTICLES = 40
TOPIC_TERMS = {
    "stocks_and_equities": ("equity", "share", "nifty", "sensex", "listed company", "scrip", "stock market"),
    "mutual_funds": ("mutual fund", "amc", "nav", "sip"),
    "bonds_and_treasury": ("bond", "treasury bill", "t-bill", "government security", "government stock", "g-sec", "yield"),
    "gold": ("gold", "sovereign gold bond", "sgb"),
    "ipo_and_public_issues": ("ipo", "public issue", "offer document", "listing"),
    "investor_protection": ("investor protection", "investor awareness", "fraud", "scam", "mis-selling", "grievance"),
    "monetary_policy_and_economy": ("monetary policy", "repo rate", "inflation", "exchange rate", "balance of payments", "foreign exchange reserves"),
    "regulation_and_compliance": ("circular", "regulation", "compliance", "sebi", "securities and exchange board", "order", "ruling"),
    "market_structure": ("derivative", "trading", "settlement", "market timing", "closing auction"),
}

SOURCES = (
    {
        "id": "rbi_press_releases",
        "name": "Reserve Bank of India — Press Releases",
        "url": "https://rbi.org.in/pressreleases_rss.xml",
        "host": "rbi.org.in",
    },
    {
        "id": "sebi_updates",
        "name": "SEBI — Press Releases, Circulars and Orders",
        "url": "https://www.sebi.gov.in/sebirss.xml",
        "host": "sebi.gov.in",
    },
)


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _text(element, *names):
    for child in element.iter():
        tag = child.tag.rsplit("}", 1)[-1].lower()
        if tag in names and child.text and child.text.strip():
            parser = _PlainText()
            parser.feed(child.text)
            return " ".join(" ".join(parser.parts).split())[:2000]
    return ""


def _link(element, source_host):
    for child in element.iter():
        if child.tag.rsplit("}", 1)[-1].lower() != "link":
            continue
        candidate = (child.attrib.get("href") or child.text or "").strip()
        parsed = urlparse(candidate)
        if parsed.scheme == "https" and (parsed.hostname or "").lower().removeprefix("www.") == source_host:
            return candidate
    return ""


def _published(element):
    raw = _text(element, "pubdate", "published", "updated", "date")
    if not raw:
        return None
    try:
        value = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _topics(title, summary):
    text = f"{title} {summary}".casefold()
    return [topic for topic, terms in TOPIC_TERMS.items() if any(term in text for term in terms)]


def _feed_items(source):
    request = Request(source["url"], headers={"User-Agent": "FinGuidePlus/0.1 (+local personal finance research)", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with urlopen(request, timeout=8) as response:
        final_host = (urlparse(response.geturl()).hostname or "").lower().removeprefix("www.")
        if final_host != source["host"]:
            raise ValueError("Feed redirected outside its verified publisher domain.")
        payload = response.read(MAX_FEED_BYTES + 1)
    if len(payload) > MAX_FEED_BYTES:
        raise ValueError("Feed exceeded the configured size limit.")
    if b"<!DOCTYPE" in payload[:4096].upper():
        raise ValueError("Document type declarations are not accepted in feeds.")
    root = ET.fromstring(payload)
    elements = [element for element in root.iter() if element.tag.rsplit("}", 1)[-1].lower() in {"item", "entry"}]
    rows = []
    for element in elements[:MAX_ITEMS_PER_FEED]:
        title = _text(element, "title")[:500]
        link = _link(element, source["host"])
        if not title or not link:
            continue
        # Keep the feed view headline-only; the publisher owns the full text.
        summary = ""
        published = _published(element)
        normalized_title = re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()
        digest = sha256(f"{normalized_title}\n{published or ''}".encode("utf-8")).hexdigest()
        analysis = get_sentiment_analyzer().analyze(title)
        published_time = datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None
        age_days = (datetime.now(timezone.utc) - published_time).days if published_time else None
        rows.append({
            "id": digest,
            "content_hash": sha256(title.strip().encode("utf-8")).hexdigest(),
            "normalized_title": normalized_title,
            "title": title,
            "summary": summary,
            "source_name": source["name"],
            "source_url": link,
            "feed_url": source["url"],
            "published_at": published,
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "freshness_status": "fresh" if age_days is not None and 0 <= age_days <= 7 else "stale" if age_days is not None and age_days > 7 else "unknown",
            "topics": _topics(title, ""),
            "sentiment": {
                "label": analysis.label,
                "confidence": analysis.confidence,
                "model_version": analysis.model_version,
                "interpretation": "Headline text tone only; it is not an estimate of price direction or investment suitability." if analysis.label != "uncertain" else "Uncertain; no compatible local sentiment model produced a result.",
            },
        })
    return rows


def get_official_financial_updates() -> dict:
    """Fetch a small, bounded snapshot from the fixed official feed allowlist."""
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    articles_by_title = {}
    source_status = []
    for source in SOURCES:
        try:
            items = _feed_items(source)
            for item in items:
                duplicate = articles_by_title.get(item["id"])
                if duplicate is None:
                    item["additional_sources"] = []
                    articles_by_title[item["id"]] = item
                elif item["source_url"] != duplicate["source_url"]:
                    duplicate["additional_sources"].append({"source_name": item["source_name"], "source_url": item["source_url"]})
            source_status.append({"source_id": source["id"], "source_name": source["name"], "feed_url": source["url"], "status": "available", "items_returned": len(items)})
        except (URLError, TimeoutError, OSError, ValueError, ET.ParseError) as exc:
            logger.info("Official news feed unavailable (%s): %s", source["id"], type(exc).__name__)
            source_status.append({"source_id": source["id"], "source_name": source["name"], "feed_url": source["url"], "status": "unavailable", "items_returned": 0, "reason": "The publisher feed could not be read or validated just now."})
    articles = list(articles_by_title.values())
    articles.sort(key=lambda row: row["published_at"] or row["retrieved_at"], reverse=True)
    for item in articles:
        item.pop("normalized_title", None)
    return {
        "status": "available" if articles else "unavailable",
        "retrieved_at": retrieved_at,
        "sources": source_status,
        "articles": articles[:MAX_ARTICLES],
        "analysis_note": "These are official RBI/SEBI updates, not a broad news or social-media sample. Sentiment describes headline wording only, never market direction. Feed text is untrusted and is not used to create or approve recommendations.",
    }
