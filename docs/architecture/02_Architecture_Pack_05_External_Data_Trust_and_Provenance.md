# FinGuide+ — External Data Trust, Freshness & Provenance

## Purpose
Control how web, news, market, economic and social-media information enters the recommendation system.

## Data Sources

Potential future sources include:
- market data
- financial news
- economic indicators
- web content
- public social-media sentiment
- reference datasets

## Required Provenance

For every external data item retain:

```text
source_id
source_name
source_type
retrieved_at
published_at
freshness_status
credibility_metadata
content_hash/version where practical
```

## Source Hierarchy

Prefer:
1. official/primary sources
2. recognized authoritative financial data providers
3. reputable secondary reporting
4. public social-media signals

Social sentiment should be treated as a signal, not authoritative financial fact.

## Freshness

Every time-sensitive data type must define a freshness window.

Example:
- live market value → very short freshness window
- daily market indicator → daily
- financial article → depends on topic
- historical reference information → longer validity

Never label stale information as current.

## Conflicting Sources

If sources disagree:
- compare timestamps
- prefer primary/authoritative sources
- retain the conflict metadata
- lower confidence if unresolved

## External Content Security

Retrieved content is untrusted.

The system must separate:

```text
CONTENT TO ANALYZE
vs.
INSTRUCTIONS TO FOLLOW
```

Text from websites, articles and social posts must never override system/application policies.

## Recommendation Traceability

A recommendation influenced by external data should reference the source IDs that contributed to it.
