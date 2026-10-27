"""Free, source-attributed market research for Indian mutual funds.

This is a research shortlist, not an approved investment recommendation.
It uses MFapi.in as a no-key NAV transport and links users to AMFI's NAV
download page. No profile values are sent to the provider. Missing/stale
data fails closed, and asset classes without a configured reliable feed
are reported as unavailable rather than filled with estimates.
"""

from __future__ import annotations

import json
import io
import math
import os
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.models.financial_profile import FinancialProfile

MFAPI_ROOT = "https://api.mfapi.in"
MFAPI_DOCS = "https://www.mfapi.in/docs/"
AMFI_NAV_URL = "https://www.amfiindia.com/net-asset-value/nav-download"
RESEARCH_POLICY_VERSION = "mf-nav-shortlist-v1"
_CACHE_TTL_SECONDS = 30 * 60
_MAX_RESPONSE_BYTES = 5_000_000
_MIN_EMERGENCY_FUND_MONTHS = Decimal("3")
_cache: dict[str, tuple[float, object]] = {}
_EODHD_ROOT = "https://eodhd.com/api"
_EODHD_DOCS = "https://eodhd.com/financial-apis/api-for-historical-data-and-volumes"
_EODHD_CACHE_TTL_SECONDS = 20 * 60 * 60
_eodhd_cache: tuple[float, dict] | None = None
_AMFI_ROOT = "https://www.amfiindia.com/api"
_AMFI_TER_URL = "https://www.amfiindia.com/ter-of-mf-schemes"
_NIFTY_DASHBOARD_PAGE = "https://www.niftyindices.com/reports/index-dashboard"
_NIFTY_DASHBOARD_BASE = "https://www.niftyindices.com/Index_Dashboard/"
_AMFI_CACHE_TTL_SECONDS = 24 * 60 * 60
_amfi_amc_cache: tuple[float, list[dict]] | None = None
_amfi_ter_cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}
_nifty_dashboard_cache: tuple[float, dict] | None = None


class MarketDataUnavailable(Exception):
    """A provider is unavailable or returned unusable market data."""


def build_nifty50_snapshot() -> dict:
    """Return a cached, dated NIFTY 50 end-of-day snapshot when configured."""
    global _eodhd_cache
    now = time.monotonic()
    if _eodhd_cache and now - _eodhd_cache[0] < _EODHD_CACHE_TTL_SECONDS:
        return _eodhd_cache[1]

    token = os.getenv("EODHD_API_TOKEN", "").strip()
    if not token:
        return {
            "status": "unavailable",
            "reason": "EODHD_API_TOKEN is not configured for the backend.",
            "source_url": _EODHD_DOCS,
        }

    query = urlencode({
        "api_token": token,
        "fmt": "json",
        "order": "d",
        "from": (date.today() - timedelta(days=20)).isoformat(),
    })
    request = Request(
        f"{_EODHD_ROOT}/eod/NSEI.INDX?{query}",
        headers={"Accept": "application/json", "User-Agent": "FinGuidePlus/1.0"},
    )
    try:
        with urlopen(request, timeout=8) as response:
            body = response.read(500_001)
        if len(body) > 500_000:
            raise MarketDataUnavailable("The market-data response exceeded the allowed size.")
        payload = json.loads(body.decode("utf-8"))
    except HTTPError as exc:
        status = "quota_exceeded" if exc.code == 429 else "provider_rejected"
        result = {
            "status": status,
            "reason": "EODHD did not return NIFTY 50 data. Check the provider plan and daily request quota.",
            "source_url": _EODHD_DOCS,
        }
        _eodhd_cache = (now, result)
        return result
    except (URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError, MarketDataUnavailable):
        result = {
            "status": "unavailable",
            "reason": "The configured EODHD market-data feed could not be reached or returned invalid data.",
            "source_url": _EODHD_DOCS,
        }
        _eodhd_cache = (now, result)
        return result

    if not isinstance(payload, list):
        result = {
            "status": "unavailable",
            "reason": "EODHD returned no usable NIFTY 50 price history.",
            "source_url": _EODHD_DOCS,
        }
        _eodhd_cache = (now, result)
        return result

    valid_rows = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        try:
            close = Decimal(str(row.get("close")))
            open_price = Decimal(str(row.get("open")))
            high = Decimal(str(row.get("high")))
            low = Decimal(str(row.get("low")))
            price_date = date.fromisoformat(str(row.get("date")))
        except (InvalidOperation, ValueError, TypeError):
            continue
        if close > 0 and all(value.is_finite() and value > 0 for value in (close, open_price, high, low)):
            valid_rows.append({"date": price_date, "open": open_price, "high": high, "low": low, "close": close})
    valid_rows.sort(key=lambda item: item["date"], reverse=True)
    if not valid_rows or (date.today() - valid_rows[0]["date"]).days > 5:
        result = {
            "status": "stale_or_unavailable",
            "reason": "No recent NIFTY 50 end-of-day record was returned; stale prices are not shown as current.",
            "source_url": _EODHD_DOCS,
        }
        _eodhd_cache = (now, result)
        return result

    latest = valid_rows[0]
    previous = valid_rows[1] if len(valid_rows) > 1 else None
    change_percent = None
    if previous and previous["close"] > 0:
        change_percent = round(float((latest["close"] / previous["close"] - 1) * 100), 2)
    result = {
        "status": "available",
        "index_name": "NIFTY 50",
        "symbol": "NSEI.INDX",
        "data_as_of": latest["date"].isoformat(),
        "open": str(latest["open"]),
        "high": str(latest["high"]),
        "low": str(latest["low"]),
        "close": str(latest["close"]),
        "previous_close_change_percent": change_percent,
        "data_frequency": "End of day; not intraday or live",
        "source_name": "EODHD end-of-day market data",
        "source_url": _EODHD_DOCS,
    }
    _eodhd_cache = (now, result)
    return result


def _json_from_provider(path: str, *, query: dict[str, str] | None = None) -> object:
    url = f"{MFAPI_ROOT}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    now = time.monotonic()
    cached = _cache.get(url)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    request = Request(url, headers={"Accept": "application/json", "User-Agent": "FinGuidePlus/1.0"})
    try:
        with urlopen(request, timeout=8) as response:
            body = response.read(_MAX_RESPONSE_BYTES + 1)
        if len(body) > _MAX_RESPONSE_BYTES:
            raise MarketDataUnavailable("Market data response exceeded the allowed size.")
        payload = json.loads(body.decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MarketDataUnavailable("The mutual-fund NAV source is temporarily unavailable.") from exc

    _cache[url] = (now, payload)
    return payload


def _nav_history(scheme_code: int) -> tuple[dict, list[tuple[date, Decimal]]]:
    payload = _json_from_provider(f"/mf/{scheme_code}")
    if not isinstance(payload, dict) or payload.get("status") != "SUCCESS":
        raise MarketDataUnavailable("The NAV source returned an invalid scheme response.")
    meta = payload.get("meta")
    rows = payload.get("data")
    if not isinstance(meta, dict) or not isinstance(rows, list):
        raise MarketDataUnavailable("The NAV source returned incomplete scheme data.")

    history: list[tuple[date, Decimal]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            nav = Decimal(str(row.get("nav")))
            nav_date = datetime.strptime(str(row.get("date")), "%d-%m-%Y").date()
        except (InvalidOperation, ValueError, TypeError):
            continue
        if nav > 0 and nav.is_finite():
            history.append((nav_date, nav))
    history.sort(key=lambda item: item[0])
    if not history:
        raise MarketDataUnavailable("No valid NAV history was returned for this scheme.")
    return meta, history


def get_latest_scheme_nav(scheme_code: int) -> dict:
    """Return a recent NAV quote or fail closed when feed data is stale."""
    meta, history = _nav_history(scheme_code)
    nav_date, nav = history[-1]
    if (date.today() - nav_date).days > 5:
        raise MarketDataUnavailable("The scheme NAV is stale; current valuation is unavailable.")
    return {
        "scheme_name": str(meta.get("scheme_name") or ""),
        "scheme_category": str(meta.get("scheme_category") or "Unknown"),
        "nav": str(nav),
        "date": nav_date.isoformat(),
    }


def _amfi_json(url: str) -> object:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 FinGuidePlus/1.0"})
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read(5_000_001)
        if len(body) > 5_000_000:
            raise MarketDataUnavailable("AMFI TER response exceeded the allowed size.")
        return json.loads(body.decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MarketDataUnavailable("AMFI TER data is temporarily unavailable.") from exc


def _amfi_amcs() -> list[dict]:
    global _amfi_amc_cache
    now = time.monotonic()
    if _amfi_amc_cache and now - _amfi_amc_cache[0] < _AMFI_CACHE_TTL_SECONDS:
        return _amfi_amc_cache[1]
    payload = _amfi_json(f"{_AMFI_ROOT}/populate-mf")
    if not isinstance(payload, list):
        raise MarketDataUnavailable("AMFI did not return its mutual-fund provider list.")
    records = [row for row in payload if isinstance(row, dict) and row.get("mfId") and row.get("mfName")]
    _amfi_amc_cache = (now, records)
    return records


def _amfi_ter_rows(amc_id: str, month: str) -> list[dict]:
    now = time.monotonic()
    key = (amc_id, month)
    cached = _amfi_ter_cache.get(key)
    if cached and now - cached[0] < _AMFI_CACHE_TTL_SECONDS:
        return cached[1]
    query = urlencode({"MF_ID": amc_id, "Month": month, "strCat": "-1", "strType": "1", "page": "1", "pageSize": "10000"})
    payload = _amfi_json(f"{_AMFI_ROOT}/populate-te-rdata-revised?{query}")
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise MarketDataUnavailable("AMFI returned an invalid TER report.")
    rows = [row for row in payload["data"] if isinstance(row, dict)]
    _amfi_ter_cache[key] = (now, rows)
    return rows


def _scheme_family_key(value: str) -> str:
    normalized = value.casefold()
    normalized = re.sub(r"\b(direct|regular|plan|growth|idcw|dividend|bonus|option|reinvestment)\b", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def _category_key(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _get_scheme_ter(meta: dict) -> dict:
    fund_house = str(meta.get("fund_house") or "").strip()
    scheme_name = str(meta.get("scheme_name") or "").strip()
    if not fund_house or not scheme_name:
        return {"status": "unavailable", "reason": "Fund house or scheme name was not supplied by the NAV source.", "source_url": _AMFI_TER_URL}
    try:
        amcs = _amfi_amcs()
    except MarketDataUnavailable as exc:
        return {"status": "unavailable", "reason": str(exc), "source_url": _AMFI_TER_URL}
    amc_key = _category_key(fund_house)
    amc = next((row for row in amcs if _category_key(str(row.get("mfName") or "")) == amc_key), None)
    if amc is None:
        return {"status": "unavailable", "reason": "Could not match the provider fund house to AMFI's TER provider list.", "source_url": _AMFI_TER_URL}

    today = date.today()
    month_dates = [today.replace(day=1) - timedelta(days=30 * offset) for offset in range(3)]
    # The AMFI portal may take several seconds per month. Fetch the small
    # three-month fallback window concurrently so an on-demand analysis does
    # not serialize three slow provider round trips.
    with ThreadPoolExecutor(max_workers=3) as executor:
        ter_futures = {
            month_date.strftime("%m-%Y"): executor.submit(
                _amfi_ter_rows, str(amc["mfId"]), month_date.strftime("%m-%Y")
            )
            for month_date in month_dates
        }
    target_name = _scheme_family_key(scheme_name)
    target_category = _category_key(str(meta.get("scheme_category") or ""))
    for month_date in month_dates:
        month = month_date.strftime("%m-%Y")
        try:
            rows = ter_futures[month].result()
        except MarketDataUnavailable:
            continue
        matches = [row for row in rows if _scheme_family_key(str(row.get("Scheme_Name") or "")) == target_name]
        if target_category:
            category_matches = [row for row in matches if _category_key(str(row.get("SchemeCat_Desc") or "")) == target_category]
            if category_matches:
                matches = category_matches
        if not matches:
            continue
        # AMFI TER reports are separated into direct/regular columns. The
        # presented scheme is direct growth because this app filters to it.
        values = []
        for row in matches:
            try:
                rate = Decimal(str(row.get("D_TER")))
                ter_date = datetime.fromisoformat(str(row.get("TER_Date")).replace("Z", "+00:00")).date()
            except (InvalidOperation, ValueError, TypeError):
                continue
            if rate.is_finite() and rate >= 0:
                values.append((ter_date, rate, row))
        if not values:
            continue
        ter_date, rate, row = max(values, key=lambda item: item[0])
        age_days = (today - ter_date).days
        return {
            "status": "available" if 0 <= age_days <= 14 else "stale",
            "ter_percent": str(rate) if 0 <= age_days <= 14 else None,
            "latest_reported_ter_percent": str(rate),
            "plan": "Direct",
            "data_as_of": ter_date.isoformat(),
            "base_expense_ratio_percent": row.get("D_BER"),
            "brokerage_cost_percent": row.get("D_BrokerageCost"),
            "transaction_cost_percent": row.get("D_TransactionCost"),
            "statutory_levies_percent": row.get("D_StatutoryLevies"),
            "source_name": "AMFI daily TER disclosure",
            "source_url": _AMFI_TER_URL,
            "fund_house": fund_house,
        }
    return {"status": "unavailable", "reason": "No unambiguous current direct-plan TER row matched this scheme name and category.", "source_url": _AMFI_TER_URL}


def _nifty50_monthly_tri_dashboard() -> dict:
    """Read NIFTY 50 TRI returns from NSE Indices' latest monthly dashboard PDF."""
    global _nifty_dashboard_cache
    now = time.monotonic()
    if _nifty_dashboard_cache and now - _nifty_dashboard_cache[0] < _AMFI_CACHE_TTL_SECONDS:
        return _nifty_dashboard_cache[1]

    try:
        page_request = Request(_NIFTY_DASHBOARD_PAGE, headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0 FinGuidePlus/1.0"})
        with urlopen(page_request, timeout=15) as response:
            page = response.read(2_000_001)
        if len(page) > 2_000_000:
            raise MarketDataUnavailable("NIFTY dashboard listing exceeded the allowed response size.")
        page_text = page.decode("utf-8", errors="replace")
        report_names = re.findall(r"Index_Dashboard_([A-Z]{3})(20\d{2})\.pdf", page_text, flags=re.IGNORECASE)
        month_number = {name.upper(): index for index, name in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
        reports = [(int(year), month_number.get(month.upper(), 0), month.upper(), int(year)) for month, year in report_names]
        reports = [item for item in reports if item[1] > 0]
        if not reports:
            raise MarketDataUnavailable("No monthly NIFTY equity dashboard is currently listed.")
        _, month_num, month_name, year = max(reports)
        report_url = f"{_NIFTY_DASHBOARD_BASE}Index_Dashboard_{month_name}{year}.pdf"
        report_request = Request(report_url, headers={"Accept": "application/pdf", "User-Agent": "Mozilla/5.0 FinGuidePlus/1.0"})
        with urlopen(report_request, timeout=20) as response:
            pdf_bytes = response.read(8_000_001)
        if len(pdf_bytes) > 8_000_000 or not pdf_bytes.startswith(b"%PDF"):
            raise MarketDataUnavailable("The latest NIFTY dashboard PDF was invalid or too large.")
        reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
        if len(reader.pages) > 20:
            raise MarketDataUnavailable("The NIFTY dashboard PDF had an unexpected page count.")
        report_text = "\n".join(page.extract_text(extraction_mode="layout") or "" for page in reader.pages)
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, ValueError, OSError, PdfReadError) as exc:
        raise MarketDataUnavailable("The official monthly NIFTY TRI dashboard is temporarily unavailable.") from exc

    date_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(20\d{2})", report_text, re.IGNORECASE)
    row_match = re.search(r"(?im)^\s*Nifty\s+50\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\b", report_text)
    if not date_match or not row_match or "Based on Total Return Index" not in report_text:
        raise MarketDataUnavailable("The official NIFTY dashboard did not contain a verifiable NIFTY 50 TRI row.")
    report_date = date(int(date_match.group(3)), month_number[date_match.group(1)[:3].upper()], int(date_match.group(2)))
    if (date.today() - report_date).days < 0 or (date.today() - report_date).days > 45:
        raise MarketDataUnavailable("The latest official NIFTY TRI dashboard is more than 45 days old.")
    returns = [float(row_match.group(index)) for index in range(1, 6)]
    result = {
        "report_date": report_date,
        "returns": {"1y": returns[2], "3y": returns[3], "5y": returns[4]},
        "source_url": report_url,
    }
    _nifty_dashboard_cache = (now, result)
    return result


def _matched_cagr(history: list[tuple[date, Decimal]], reference_date: date, years: int) -> float | None:
    latest = next(((point_date, value) for point_date, value in reversed(history) if point_date <= reference_date), None)
    if latest is None:
        return None
    latest_date, latest_value = latest
    target = latest_date - timedelta(days=round(365.2425 * years))
    prior = next(((point_date, value) for point_date, value in reversed(history) if point_date <= target), None)
    if prior is None:
        return None
    elapsed = (latest_date - prior[0]).days / 365.2425
    return float(((latest_value / prior[1]) ** (Decimal(1) / Decimal(str(elapsed))) - 1) * 100) if elapsed > 0 else None


def _matched_absolute_return(history: list[tuple[date, Decimal]], reference_date: date, years: int) -> float | None:
    latest = next(((point_date, value) for point_date, value in reversed(history) if point_date <= reference_date), None)
    if latest is None:
        return None
    latest_date, latest_value = latest
    target = latest_date - timedelta(days=round(365.2425 * years))
    prior = next(((point_date, value) for point_date, value in reversed(history) if point_date <= target), None)
    if prior is None or prior[1] <= 0:
        return None
    return float((latest_value / prior[1] - 1) * 100)


def build_fund_analysis(scheme_code: int) -> dict:
    """Return on-demand TER and only a benchmark mapping we can verify."""
    meta, history = _nav_history(scheme_code)
    latest_date = history[-1][0]
    nav_age_days = (date.today() - latest_date).days
    nav_is_stale = nav_age_days > 5 or nav_age_days < 0
    name = str(meta.get("scheme_name") or "")
    is_nifty50_index = "nifty 50" in name.casefold() and "index" in name.casefold() and "direct" in name.casefold()
    result = {
        "scheme_code": scheme_code,
        "scheme_name": name,
        "scheme_category": str(meta.get("scheme_category") or "Unknown"),
        "nav_data_as_of": latest_date.isoformat(),
        "nav_status": "stale" if nav_is_stale else "available",
        "nav_age_days": nav_age_days,
        "expense_ratio": _get_scheme_ter(meta),
        "benchmark": {"status": "unavailable", "reason": "The exact benchmark has not been verified for this scheme. FinGuide does not substitute an unrelated index.", "source_url": "https://www.niftyindices.com/reports/historical-data"},
        "analysis_notice": "Historical comparisons describe past data and are not forecasts or investment instructions.",
    }
    if not is_nifty50_index:
        return result
    if nav_is_stale:
        result["benchmark"]["reason"] = (
            f"Fund NAV history is {nav_age_days} days old. Benchmark comparison is withheld until recent NAV data is available."
        )
        return result
    try:
        dashboard = _nifty50_monthly_tri_dashboard()
        report_date = dashboard["report_date"]
        fund_periods = {
            "1y": _matched_absolute_return(history, report_date, 1),
            "3y": _matched_cagr(history, report_date, 3),
            "5y": _matched_cagr(history, report_date, 5),
        }
        comparisons = {}
        for period in ("1y", "3y", "5y"):
            fund_value, index_value = fund_periods[period], dashboard["returns"][period]
            comparisons[period] = {
                "fund_return_percent": round(fund_value, 2) if fund_value is not None else None,
                "benchmark_return_percent": round(index_value, 2),
                "difference_percentage_points": round(fund_value - index_value, 2) if fund_value is not None and index_value is not None else None,
            }
        result["benchmark"] = {
            "status": "available",
            "name": "NIFTY 50 TRI",
            "data_as_of": report_date.isoformat(),
            "comparisons": comparisons,
            "source_name": "NSE Indices monthly equity dashboard (returns based on TRI)",
            "source_url": dashboard["source_url"],
            "method_note": "Compared at the official dashboard month-end. The 1-year return is absolute; 3-year and 5-year returns are CAGR. Fund NAV uses the nearest available observations on or before matched dates. This is not a tracking-error estimate.",
        }
    except MarketDataUnavailable as exc:
        result["benchmark"]["reason"] = str(exc)
    return result


def _period_return(history: list[tuple[date, Decimal]], years: int) -> float | None:
    latest_date, latest_nav = history[-1]
    target_date = latest_date - timedelta(days=round(365.2425 * years))
    # Histories are sorted oldest-first. Use the closest NAV on or before
    # the lookback date; taking the first older row incorrectly reused the
    # scheme's earliest NAV for every return horizon.
    prior = next(((d, nav) for d, nav in reversed(history) if d <= target_date), None)
    if prior is None:
        return None
    elapsed_years = (latest_date - prior[0]).days / 365.2425
    if elapsed_years <= 0 or prior[1] <= 0:
        return None
    return float(((latest_nav / prior[1]) ** (Decimal(1) / Decimal(str(elapsed_years))) - 1) * 100)


def _risk_stats(history: list[tuple[date, Decimal]], years: int = 3) -> tuple[float | None, float | None]:
    cutoff = history[-1][0] - timedelta(days=365 * years)
    recent = [(d, nav) for d, nav in history if d >= cutoff]
    daily_returns: list[float] = []
    peak: Decimal | None = None
    max_drawdown = 0.0
    previous: Decimal | None = None
    for _, nav in recent:
        if previous is not None and previous > 0:
            daily_returns.append(float(nav / previous - 1))
        previous = nav
        peak = nav if peak is None else max(peak, nav)
        if peak > 0:
            max_drawdown = min(max_drawdown, float(nav / peak - 1))
    volatility = statistics.stdev(daily_returns) * math.sqrt(252) * 100 if len(daily_returns) > 20 else None
    drawdown = max_drawdown * 100 if len(recent) > 1 else None
    return volatility, drawdown


def _risk_profile(profile: FinancialProfile, horizon_override: int | None = None) -> tuple[str | None, list[str]]:
    risk_raw = (profile.risk_preference or "").strip().lower()
    horizon = horizon_override if horizon_override is not None else profile.investment_horizon_years
    missing = []
    if risk_raw not in {"low", "conservative", "moderate", "medium", "balanced", "high", "aggressive"}:
        missing.append("risk_preference")
    if horizon is None or horizon <= 0:
        missing.append("investment_horizon_years")
    risk = "low" if risk_raw in {"low", "conservative"} else "medium" if risk_raw in {"moderate", "medium", "balanced"} else "high" if risk_raw in {"high", "aggressive"} else None
    return risk, missing


def _candidate_metrics(code: int, search_name: str, research_group: str) -> tuple[dict | None, bool]:
    try:
        meta, history = _nav_history(code)
    except MarketDataUnavailable:
        return None, False
    latest_date, latest_nav = history[-1]
    if (date.today() - latest_date).days > 5:
        return None, True
    name = str(meta.get("scheme_name") or search_name)
    if "direct" not in name.lower() or "growth" not in name.lower():
        return None, False
    cagr_1y = _period_return(history, 1)
    cagr_3y = _period_return(history, 3)
    cagr_5y = _period_return(history, 5)
    if cagr_3y is None:
        return None, False
    volatility, max_drawdown = _risk_stats(history)
    return ({
        "scheme_code": code,
        "scheme_name": name,
        "scheme_category": str(meta.get("scheme_category") or "Unknown"),
        "research_group": research_group,
        "latest_nav": str(latest_nav),
        "nav_date": latest_date.isoformat(),
        "return_1y_percent": round(cagr_1y, 2) if cagr_1y is not None else None,
        "return_3y_cagr_percent": round(cagr_3y, 2),
        "return_5y_cagr_percent": round(cagr_5y, 2) if cagr_5y is not None else None,
        "annualized_daily_volatility_percent": round(volatility, 2) if volatility is not None else None,
        "max_drawdown_3y_percent": round(max_drawdown, 2) if max_drawdown is not None else None,
        "source_url": f"https://api.mfapi.in/mf/{code}",
        "source_name": "MFapi.in (NAV data); see AMFI primary reference",
    }, False)


def _rank_category_candidates(candidates: list[dict], risk: str | None) -> None:
    """Add transparent, within-category historical research ranks in place."""
    if risk == "high":
        weights = {"return_3y_cagr_percent": 0.45, "positive_period_rate": 0.25, "max_drawdown_3y_percent": 0.20, "annualized_daily_volatility_percent": 0.10}
        risk_label = "higher risk"
    elif risk == "low":
        weights = {"return_3y_cagr_percent": 0.10, "positive_period_rate": 0.20, "max_drawdown_3y_percent": 0.40, "annualized_daily_volatility_percent": 0.30}
        risk_label = "lower risk"
    else:
        weights = {"return_3y_cagr_percent": 0.30, "positive_period_rate": 0.25, "max_drawdown_3y_percent": 0.25, "annualized_daily_volatility_percent": 0.20}
        risk_label = "moderate risk"
    basis = (
        f"{risk_label} weights: 3-year return {weights['return_3y_cagr_percent']:.0%}, "
        f"positive 1/3/5-year periods {weights['positive_period_rate']:.0%}, "
        f"smaller 3-year drawdown {weights['max_drawdown_3y_percent']:.0%}, "
        f"lower 3-year volatility {weights['annualized_daily_volatility_percent']:.0%}."
    )
    categories: dict[str, list[dict]] = {}
    for item in candidates:
        period_returns = [item.get("return_1y_percent"), item.get("return_3y_cagr_percent"), item.get("return_5y_cagr_percent")]
        available = [value for value in period_returns if value is not None]
        item["positive_period_rate"] = round(sum(value > 0 for value in available) / len(available), 3) if available else None
        item["positive_periods"] = sum(value > 0 for value in available)
        item["periods_available"] = len(available)
        item["relative_rank"] = None
        item["peer_count"] = 1
        item["research_score"] = None
        item["score_basis"] = "A relative score is shown only when at least two comparable candidates are available in this scheme category."
        categories.setdefault(str(item.get("scheme_category") or "Unknown"), []).append(item)

    for peers in categories.values():
        for item in peers:
            item["peer_count"] = len(peers)
        if len(peers) < 2:
            continue
        dimensions = [dimension for dimension in weights if all(item.get(dimension) is not None for item in peers)]
        if not dimensions:
            continue
        total_weight = sum(weights[dimension] for dimension in dimensions)
        values = {dimension: [float(item[dimension]) for item in peers] for dimension in dimensions}
        scores: list[tuple[dict, float]] = []
        for item in peers:
            score = 0.0
            for dimension in dimensions:
                low_value, high_value = min(values[dimension]), max(values[dimension])
                normalized = 0.5 if high_value == low_value else (float(item[dimension]) - low_value) / (high_value - low_value)
                # Drawdown values are negative, so a less negative value is
                # already higher/better. Volatility is lower/better.
                if dimension == "annualized_daily_volatility_percent":
                    normalized = 1.0 - normalized
                score += normalized * weights[dimension] / total_weight
            scores.append((item, score * 100))
        scores.sort(key=lambda pair: (-pair[1], pair[0]["scheme_name"].casefold()))
        for index, (item, score) in enumerate(scores, start=1):
            item["relative_rank"] = index
            item["research_score"] = round(score, 1)
            item["score_basis"] = basis


def _candidate_research_reason(candidate: dict, risk: str | None) -> str:
    rank = candidate.get("relative_rank")
    peers = candidate.get("peer_count", 1)
    if rank is None:
        return (
            f"NAV history passed the basic screen, but only {peers} comparable candidate(s) "
            "were available in this scheme category, so no relative score was assigned."
        )
    risk_phrase = {
        "low": "the score gives greater weight to drawdown and volatility",
        "medium": "the score balances historical return and risk measures",
        "high": "the score gives greater weight to historical return",
    }.get(risk, "the score uses the recorded risk preference")
    return (
        f"Ranked {rank} of {peers} screened candidates in this scheme category; "
        f"{risk_phrase}. This is a comparison of past NAV data, not future performance or a buy instruction."
    )


def build_research_shortlist(profile: FinancialProfile, *, goal_horizon_years: int | None = None) -> dict:
    """Build an explicitly non-advisory, profile-gated research snapshot."""
    risk, missing = _risk_profile(profile, goal_horizon_years)
    for field_name in ("fixed_expenses", "variable_expenses", "emergency_fund_amount"):
        if getattr(profile, field_name) is None:
            missing.append(field_name)
    updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    unavailable = [
        {"asset_class": "individual_stocks", "status": "unavailable", "reason": "A free, verified single-stock feed is not yet configured. NIFTY 50 end-of-day index data is shown separately when EODHD is configured.", "source_url": "https://www.nseindia.com/static/market-data/nse-data-policy"},
        {"asset_class": "individual_bonds", "status": "unavailable", "reason": "Free official RBI market-rate and auction information is useful for reference, but no verified bond quote feed is integrated here.", "source_url": "https://rbiretaildirect.org.in/"},
        {"asset_class": "gold_spot_price", "status": "unavailable", "reason": "No free, redistributable official India spot-price feed is configured. Gold mutual-fund NAV candidates may appear when the free NAV source returns them."},
        {"asset_class": "ipo_calendar_and_subscription", "status": "unavailable", "reason": "No verified free IPO calendar and subscription feed is integrated.", "source_url": "https://www.nseindia.com/market-data/all-upcoming-issues-ipo"},
    ]
    response = {
        "status": "needs_profile" if missing else "ready",
        "policy_version": RESEARCH_POLICY_VERSION,
        "generated_at": updated_at,
        "profile_fields_needed": missing,
        "research_notice": "Research candidates for user/adviser review; not a buy/sell instruction or a forecast. Historical NAV returns are not expected returns.",
        "provider": {"name": "MFapi.in", "url": MFAPI_DOCS, "primary_data_reference": {"name": "AMFI NAV download", "url": AMFI_NAV_URL}},
        "index_snapshot": build_nifty50_snapshot(),
        "criteria": ["Emergency fund coverage must be at least three months of recorded expenses", "Only moderate/aggressive risk preferences and horizons of at least five years pass the equity-fund screen", "Searches Nifty 50 index, large-cap, flexi-cap, mid-cap, debt-fund, and gold-fund schemes; equity categories remain subject to profile gates", "Direct plan and growth option", "At least 3 years of NAV history", "Historical return, positive 1/3/5-year periods, volatility, and drawdown are compared within each scheme category; scores are research rankings, not expected returns or best-buy claims."],
        "candidates": [],
        "unavailable_assets": unavailable,
        "limitations": ["Mutual-fund NAVs and the NIFTY 50 snapshot are end-of-day data, not intraday or real-time quotes.", "NAV-only screening does not include expense ratio, benchmark-relative tracking error, portfolio holdings, tax, or transaction costs.", "SIP is a contribution method, not a separate asset or market feed. This screen does not calculate a user's SIP outcome or predict returns.", "The NIFTY 50 is shown as an index snapshot; it is not an index-fund recommendation.", "Debt and gold mutual-fund NAVs are fund data, not individual bond yields or gold spot prices."],
    }
    if missing:
        return response

    monthly_expenses = Decimal(str(profile.fixed_expenses)) + Decimal(str(profile.variable_expenses))
    if monthly_expenses <= 0:
        response["status"] = "needs_profile"
        response["profile_fields_needed"] = ["verify_monthly_expenses"]
        return response
    emergency_coverage = Decimal(str(profile.emergency_fund_amount)) / monthly_expenses
    response["suitability_gate"] = {
        "status": "passed" if emergency_coverage >= _MIN_EMERGENCY_FUND_MONTHS else "hold",
        "emergency_fund_coverage_months": round(float(emergency_coverage), 2),
        "minimum_months": int(_MIN_EMERGENCY_FUND_MONTHS),
        "detail": "Equity research is held until emergency savings cover at least three months of recorded expenses." if emergency_coverage < _MIN_EMERGENCY_FUND_MONTHS else "The minimum emergency-fund coverage check passed.",
    }
    if emergency_coverage < _MIN_EMERGENCY_FUND_MONTHS:
        response["status"] = "priority_financial_foundation"
        return response

    horizon = int(goal_horizon_years if goal_horizon_years is not None else (profile.investment_horizon_years or 0))
    if risk == "low" or horizon < 5:
        response["status"] = "no_equity_shortlist"
        response["limitations"].append("Equity-fund candidates are withheld for a low-risk profile or a horizon under five years; the non-equity NAV research categories below are not a substitute for suitability review.")

    schemes: dict[int, tuple[str, str]] = {}
    queries = [
        ("Nifty 50 Index Fund Direct Growth", "Nifty 50 index funds", ("nifty 50", "index fund")),
        ("Large Cap Fund Direct Growth", "Large-cap equity funds", ("large cap", "large-cap")),
        ("Flexi Cap Fund Direct Growth", "Flexi-cap equity funds", ("flexi cap", "flexicap", "flexi-cap")),
        ("Mid Cap Fund Direct Growth", "Mid-cap equity funds", ("mid cap", "mid-cap", "midcap")),
        ("Short Duration Debt Fund Direct Growth", "Debt mutual funds", ("short duration", "debt")),
        ("Gilt Fund Direct Growth", "Debt mutual funds", ("gilt",)),
        ("Gold Fund Direct Growth", "Gold mutual funds", ("gold",)),
    ]
    if risk == "low" or horizon < 5:
        queries = [item for item in queries if item[1] in {"Debt mutual funds", "Gold mutual funds"}]
    elif risk != "high" or horizon < 7:
        queries = [item for item in queries if item[1] != "Mid-cap equity funds"]
    max_per_research_group = 5
    for query, research_group, required_terms in queries:
        results = _json_from_provider("/mf/search", query={"q": query})
        if not isinstance(results, list):
            continue
        for item in results:
            if not isinstance(item, dict):
                continue
            name = str(item.get("schemeName") or "").strip()
            code = item.get("schemeCode")
            lower = name.lower()
            if not isinstance(code, int) or not ("direct" in lower and "growth" in lower):
                continue
            if not any(term in lower for term in required_terms):
                continue
            if any(word in lower for word in ("dividend", "idcw", "bonus", "regular")):
                continue
            if code in schemes:
                continue
            schemes[code] = (name, research_group)
            if sum(group == research_group for _, group in schemes.values()) >= max_per_research_group:
                break
            if len(schemes) >= 35:
                break
        if len(schemes) >= 35:
            break

    candidates = []
    stale_count = 0
    scheme_items = list(schemes.items())[:35]
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = executor.map(lambda item: _candidate_metrics(item[0], item[1][0], item[1][1]), scheme_items)
        for candidate, stale in results:
            if candidate is not None:
                candidates.append(candidate)
            stale_count += int(stale)

    _rank_category_candidates(candidates, risk)
    for candidate in candidates:
        candidate["research_reason"] = _candidate_research_reason(candidate, risk)
    response["ranking_method"] = "Candidates are compared only with screened peers in the same provider-reported scheme category. The score balances historical return and risk measures using the recorded risk preference; missing peer comparisons receive no score."
    response["candidates"] = sorted(candidates, key=lambda item: (item["research_group"], item["scheme_category"].casefold(), item["relative_rank"] is None, item["relative_rank"] or 999, item["scheme_name"].casefold()))
    if not candidates:
        response["status"] = "market_data_unavailable"
        response["limitations"].append("No current, sufficiently complete Nifty index-fund NAV histories were returned. No instrument was selected.")
    else:
        response["status"] = "research_candidates"
        response["market_data_as_of"] = max(item["nav_date"] for item in candidates)
    response["limitations"].append("The NAV source is a third-party API; confirm scheme details and latest NAV on the linked AMFI/AMC sources before acting.")
    response["limitations"].append("The relative rank covers only the returned, NAV-screened candidates and is not a complete market-wide comparison; fund expenses, holdings, benchmark tracking, taxes, and transaction costs are not included.")
    if stale_count:
        response["stale_schemes_excluded"] = stale_count
    return response


def build_mutual_fund_goal_plan(profile: FinancialProfile, goal: dict) -> dict:
    """Pair a zero-growth savings pace calculation with a goal-horizon shortlist.

    The arithmetic is a budgeting baseline, not an investment return forecast.
    """
    years = int(goal["years"])
    target = Decimal(str(goal["target_amount"]))
    current = Decimal(str(goal["current_savings"]))
    monthly = Decimal(str(goal["monthly_contribution"]))
    months = years * 12
    remaining = max(Decimal("0"), target - current)
    monthly_baseline = (remaining / months).quantize(Decimal("0.01"))
    monthly_gap = max(Decimal("0"), monthly_baseline - monthly).quantize(Decimal("0.01"))
    if remaining == 0:
        pace_status = "goal_amount_already_saved"
        pace_message = "The amount you entered as already saved meets this goal target."
    elif monthly >= monthly_baseline:
        pace_status = "meets_zero_growth_baseline"
        pace_message = "Your planned monthly contribution meets the simple zero-growth savings baseline."
    else:
        pace_status = "below_zero_growth_baseline"
        pace_message = "Your planned monthly contribution is below the simple zero-growth savings baseline."

    try:
        research = build_research_shortlist(profile, goal_horizon_years=years)
    except MarketDataUnavailable as exc:
        research = {
            "status": "market_data_unavailable",
            "candidates": [],
            "research_notice": "The savings baseline is available, but product research could not verify current market data.",
            "profile_fields_needed": [],
            "unavailable_assets": [{"asset_class": "mutual_funds", "status": "unavailable", "reason": str(exc)}],
            "limitations": ["Refresh research later or verify scheme information on AMFI and the fund provider's official website."],
        }
    plan = {
        "goal_name": str(goal["goal_name"]).strip(),
        "target_amount": str(target.quantize(Decimal("0.01"))),
        "current_savings": str(current.quantize(Decimal("0.01"))),
        "remaining_amount": str(remaining.quantize(Decimal("0.01"))),
        "years": years,
        "months": months,
        "planned_monthly_contribution": str(monthly.quantize(Decimal("0.01"))),
        "monthly_savings_baseline": str(monthly_baseline),
        "monthly_baseline_gap": str(monthly_gap),
        "pace_status": pace_status,
        "pace_message": pace_message,
        "calculation_note": "This baseline assumes zero investment growth and excludes inflation, taxes, fees, and changes in contributions. It is not a return forecast or a required SIP amount.",
        "research_note": "Fund candidates are screened using your profile and this goal's time horizon. They are research candidates, not personalized buy/sell advice.",
    }
    return {"goal_plan": plan, "market_research": research}
