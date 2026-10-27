# FinGuide+ Future Enhancement Checkpoint

**Checkpoint date:** 17 October 2026  
**Status:** Private local prototype; source-attributed NAV/index research and RBI/SEBI headlines with local FinBERT tone are running. Gemini can receive relevant public NIFTY and official-headline context for current-market questions. Broader asset coverage, education retrieval, and permissioned profile-aware chat remain future work.

## Product direction

FinGuide+ should be a conversational financial learning and discussion assistant. Its first real-user focus is:

1. **Personalized financial discussion** using the user's permitted profile and spending context.
2. **Current-market questions** answered with fresh, attributable data.
3. **General financial education** that explains terms and topics in plain language.

Recommendations remain a separate, optional capability. Specific personalized buy/sell recommendations are outside the initial scope until the product, data, evaluation, and regulatory boundaries are settled.

## Decisions agreed

- **Launch geography:** India first.
- **Initial market coverage:** stocks, mutual funds, SIPs, and IPOs.
- **Market-data freshness:** daily.
- **Personal context:** conversational financial information may be extracted to understand the user's current profile. Extracted facts remain reviewable candidates; they do not silently overwrite the profile. Profile data is not sent to an external LLM in the first integration.
- **Initial LLM provider:** Google Gemini behind the existing provider interface. OpenAI remains available as an alternative; provider selection does not change the rest of the application architecture.

## Current baseline

The current architecture already has useful foundations: a replaceable `ChatbotEngine` interface, persisted conversations, user-scoped profile and transaction APIs, deterministic financial metrics, evidence provenance fields, recommendation safety gates, feedback, evaluation, and privacy controls.

The following capabilities are **not live in the current build**:

- OpenAI and Gemini API adapters are available behind the provider factory. The local runtime uses Gemini; a successful conversation was observed, with a bounded fallback model for intermittent 503 overloads. External chat requires fresh, provider-specific consent.
- Local market research now reads free-source mutual-fund NAV and configured end-of-day index data; results are source-dated and not real-time.
- The local Recommendations page can fetch RBI and SEBI RSS headlines, preserve publisher/source links and retrieval time, tag topics, deduplicate matching titles, and mark publication freshness. These items are not used for recommendations.
- Local CPU FinBERT analyzes official headline wording; it is not market direction. The feed is official RBI/SEBI updates, not broad media or social sentiment.
- News summarization and current-news chat retrieval are not implemented.
- Evidence submitted through the API is marked unverified and is not used by recommendations.
- Gemini current-market chat can use source-linked Google Search results plus the locally configured NIFTY end-of-day snapshot and selected RBI/SEBI headline snippets. The current Gemini consent policy is `1.4-ai-gemini-market-context`; a user must grant that version before provider processing. Previous turns and saved profile are excluded from market requests. Saved-profile context tools and a maintained financial-education reference collection are not implemented. Chat extraction stores local reviewable candidates and does not silently update the profile.

The frontend screens have been connected to the existing APIs, but the local database has no profile or transaction data until a user adds it.

### Brick 16 progress delivered in the local prototype

- Official RBI press-release and SEBI RSS feeds are allowlisted; feed redirects and article links are restricted to the corresponding official publisher domain.
- RSS payload size, item count, timeout, and XML document type are bounded. Full article pages are not fetched.
- Each headline includes a stable content identifier/hash, source link, publisher timestamp when supplied, retrieval timestamp, publication freshness (`fresh`, `stale`, or `unknown`), deterministic topic tags, and optional local sentiment output.
- Headlines are displayed under **Recommendations → Official financial updates**, and selected headline titles can ground relevant Gemini market questions. FinBERT output is headline tone only and does not determine suitability or recommendations.
- This is a local prototype, not a public news redistribution service. Confirm provider terms before a public release.

## Enhancement sequence

### Checkpoint 1 — Define launch boundaries

The initial geography, asset classes, daily freshness, and intended experience are agreed. Remaining boundary work includes target user groups, source coverage, detailed consent language, and the distinction between education, market discussion, and regulated investment advice. Get qualified review before offering individualized securities advice.

**Exit condition:** A short product scope states what the assistant may answer, what data it may use, and what it must decline or escalate. (Core launch choices recorded; remaining scope details are open.)

### Checkpoint 2 — Add an LLM conversation provider

Implement an LLM-backed engine behind the existing `ChatbotEngine` interface. Keep provider credentials on the backend. Preserve local conversation storage, impose request/token/cost limits, and retain the rule-based engine as a development fallback. Compare providers on answer quality, latency, privacy/retention controls, and cost before committing to one.

**Exit condition:** General finance questions get coherent multi-turn answers; outages, refusals, and limits have clear behavior; the client never sees provider credentials.

### Checkpoint 3 — Ground financial education

Create a maintained reference collection for financial concepts and educational material, with source, jurisdiction, publication/update date, and topic metadata. Retrieve relevant passages for answers and show useful citations. Keep general explanations separate from user-specific facts and current market claims.

**Exit condition:** Answers that rely on reference material identify their sources; unsupported or conflicting material is disclosed instead of guessed.

### Checkpoint 4 — Add permissioned personal context

Expose narrowly scoped, read-only tools for the assistant, such as retrieving a profile summary, calculating a spending total, or explaining a stored metric. Enforce user ownership in backend code, minimize the context sent to the model, and make it clear when personal data is being used. Financial calculations remain deterministic application code.

**Exit condition:** A user can ask a personal question and see which of their facts and calculations informed the response; cross-user access is impossible by design.

### Checkpoint 5 — Build current-market data support (Brick 15)

Choose licensed or otherwise authorized sources and define coverage for equities, mutual funds, and IPOs. Store normalized observations with instrument identity, source, currency, unit, observation time, ingestion time, and freshness/quality status. Calculate returns and comparisons in application code, not in free-form model text.

**Exit condition:** A market answer states the instrument, period, benchmark where relevant, source, and “as of” time; stale, missing, or conflicting data produces a clear limitation.

### Checkpoint 6 — Build news, web, and social analytics (Brick 16)

Ingest from approved sources. Deduplicate, identify entities/topics, preserve publication time and source provenance, and summarize retrieved material. Use FinBERT or a comparable finance sentiment model only after evaluation on representative data. Treat social sentiment as noisy opinion, never as authoritative market fact. Treat retrieved content as untrusted input that cannot override system policy.

**Exit condition:** Responses distinguish verified market facts, reported claims, and aggregate public sentiment; summaries link to their underlying sources and disclose coverage limits.

### Checkpoint 7 — Connect chat and optional recommendations

Let chat retrieve education, personal context, and current evidence according to the user's question and permissions. Keep recommendation generation as a separate downstream workflow with the existing safety/suitability gate. Add context-aware recommendations only when their input evidence and decision rules can be traced and evaluated. Use SHAP/LIME where a compatible predictive model makes those explanations meaningful; use explicit evidence and rule traces elsewhere.

**Exit condition:** Chat can explain evidence and uncertainty without turning every question into a recommendation; recommendation candidates remain auditable and safety-gated.

### Checkpoint 8 — Evaluate before wider release

Build an expert-reviewed evaluation set covering financial terms, calculations, personal-context questions, current-market questions, conflicting/stale sources, prompt injection in retrieved text, and unsupported claims. Measure factuality, calculation correctness, citation support, freshness, refusal quality, privacy boundaries, latency, and cost. Run a limited beta and review failures before expanding source coverage or recommendation behavior.

**Exit condition:** Release thresholds are defined and met; known failure modes have mitigations, owners, and monitoring.

## Architecture guardrails

- The LLM explains and converses; backend code owns identity, permissions, calculations, freshness checks, and safety decisions.
- Use retrieval for changing or source-specific knowledge; do not fine-tune market prices or use model memory as a live data feed.
- Send only the minimum personal data needed for the user's question, with explicit product consent and clear provider disclosure.
- Preserve provenance and version information for prompts, models, tools, calculations, and evidence.
- Never imply that past performance or social sentiment predicts future returns.
- Do not enable financial-product execution or specific personalized securities recommendations as an accidental side effect of chat.

## Next planning decisions

1. Which launch geography comes first?
2. Which asset classes and data freshness levels are required at launch?
3. Should the assistant use profile context only when requested, or offer it when clearly relevant and ask before using it?
4. What is the first release boundary between education, market analysis, and personalized investment advice?
5. Which market-data provider and usage license should be used for the private prototype, and what is the eventual public-app licensing budget? See `MARKET_DATA_PROVIDER_EVALUATION.md`.

This checkpoint extends the current Brick 15–17 architecture. It does not replace the architecture lock or authorize implementation by itself.
