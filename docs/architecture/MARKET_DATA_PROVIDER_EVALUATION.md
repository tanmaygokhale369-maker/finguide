# FinGuide+ India Market Data Provider Decision

**Reviewed:** 9 October 2026  
**Scope:** Brick 15 daily data for Indian equities, mutual-fund NAVs, IPOs, plus deterministic SIP calculations.

## Recommended source split

Use the official AMFI NAV download as the first mutual-fund NAV source, a licensed market-data API for equities and IPO calendar data, and application code for SIP calculations. A SIP is a contribution schedule/calculation, not a market instrument feed. Do not treat a model's web search as a price feed.

## Candidate sources

| Source | Useful coverage | Important limits |
|---|---|---|
| [AMFI NAV download](https://www.amfiindia.com/net-asset-value/nav-download) | Official Indian mutual-fund NAV reports and NAV history; daily NAVs match the user's daily-freshness requirement. | The portal offers historical downloads up to 90 days per request. Confirm reuse/redistribution terms before public display; public availability alone does not settle licensing. |
| [Twelve Data](https://twelvedata.com/docs) | One API family includes stocks, mutual funds, and an IPO calendar. Its IPO calendar costs 40 API credits/request and is available from the Grow individual plan / Venture business plan. | Individual Grow is for personal, internal, non-commercial use (currently listed at USD 79/month). Public display requires a business tier; Venture is currently listed at USD 499/month and includes external display rights. Verify NSE/BSE symbol access and the intended product's exact data entitlements before relying on it. |
| [EODHD](https://eodhd.com/financial-apis/quick-start-with-our-financial-data-apis) | Equities, funds, EOD prices, IPO calendar, and news endpoints; the provider documents exchange and symbol-list endpoints for coverage checks. | Personal packages are not commercial licenses. The provider requires a separate commercial licensing discussion for a public/commercial app. Confirm endpoint-by-endpoint Indian coverage, timeliness, and display rights before integration. |

Pricing and plans are provider-controlled and can change. The amounts above reflect the providers' published pages on the review date; they are not a purchase recommendation.

## What should be verified before choosing

1. Confirm the provider returns the specific NSE/BSE tickers, Indian mutual-fund schemes, and India IPO records FinGuide+ needs.
2. Confirm the data is end-of-day or delayed/live and label it accurately. Do not call daily close data “real time.”
3. Confirm API request quotas for a daily sync, API credit cost per endpoint, history depth, and service limits.
4. Confirm local prototype rights separately from public display/redistribution rights.
5. Add provider credentials only to the backend `.env`; never to Vite variables or the browser.

## Implementation boundary after source approval

- Normalize provider responses into instrument/event records with source, source URL, observation/publication time, fetch time, currency/unit, market/session, and payload hash.
- Keep end-of-day equity prices, NAVs, and IPO lifecycle records distinct; a change in an IPO expected date/price must update the event rather than be treated as a price observation.
- Run one daily, idempotent sync after the relevant Indian market data is published. Retain provider timestamps and report stale/missing data explicitly.
- Calculate returns and SIP projections in deterministic backend code. The LLM may explain those results but must not invent or calculate the underlying figures.
- Keep news and social ingestion as a later Brick 16 source approval, with article-level provenance and a separate evaluation plan.

## Decision needed

No paid plan or data license has been selected. For a private local prototype, Twelve Data Grow or a personal EODHD plan may be evaluated after confirming Indian coverage. A public FinGuide+ app needs an external-display/commercial license; do not launch with a personal-use key. AMFI can be implemented as a separate NAV source after reuse terms are confirmed.
