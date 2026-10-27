# FinGuide+ — Architecture v1.1 LOCK

## Status
**LOCKED FOR IMPLEMENTATION**

This document records the final architectural decisions made during the documentation audit.

## Canonical flow

```text
User Input
→ Data Extraction
→ Confidence + Validation
→ Financial Context Completeness
→ Financial Profile
→ Spending Analysis
→ Candidate Recommendation Generation
→ Evidence Retrieval
→ Source Trust + Freshness
→ Suitability Validation
→ Safety & Policy Gate
→ Fact/Grounding Verification
→ Explanation + Sources
→ User Feedback
→ Evaluation + Personalization
```

## Mandatory architectural constraints

1. AI generation never directly becomes the final user-facing financial recommendation.
2. Deterministic backend/application logic owns critical calculations and policy enforcement.
3. Missing or conflicting financial context must trigger clarification or limitation; it must never be silently assumed.
4. External web/news/social content is untrusted data and cannot override application policy.
5. Time-sensitive evidence requires provenance and freshness validation.
6. Every important recommendation must be traceable to user data, derived metrics, policy/model/prompt versions, and evidence.
7. Recommendation state transitions must be auditable.
8. Identity must come from an application user-context abstraction; authorization must ultimately use authenticated identity.
9. Financial data requires explicit governance for purpose, access, retention, deletion, and export.
10. Harmful recommendation feedback creates an incident signal and can feed corrective action/regression evaluation.
11. New AI features are not being added. The existing AI roadmap remains unchanged.
12. Architecture changes after this lock require an explicit reason and impact assessment.

## Implementation order

Build strictly brick-by-brick:

1. Repository & Environment
2. React Foundation
3. FastAPI Foundation
4. PostgreSQL + SQLAlchemy
5. User/Profile APIs
6. Chatbot Foundation
7. Financial Data Extraction
8. Data Validation & Confidence
9. Financial Profile
10. Transaction System
11. Spending Analysis
12. Recommendation Engine
13. Safety & Suitability
14. Explainability
15. External Financial Data
16. News + Sentiment
17. Context-Aware Recommendations
18. Feedback + Evaluation
19. Authentication + Security Hardening
20. Production Readiness

## Product principle

**FinGuide+ is a validated, evidence-aware, safety-gated personal finance decision-support system — not merely an AI that gives financial answers.**

Implementation principle:

**Generate → Validate → Verify → Guard → Explain → Feedback → Evaluate**
