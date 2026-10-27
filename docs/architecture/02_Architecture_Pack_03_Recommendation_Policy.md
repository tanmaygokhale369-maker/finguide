# FinGuide+ — Recommendation Policy

## Objective
Define the decision policy used before a personalized financial recommendation is displayed.

## Recommendation Pipeline

```text
User Profile
→ Context Completeness
→ Data Validation
→ Candidate Generation
→ Evidence Retrieval
→ Suitability Check
→ Safety/Policy Check
→ Explanation
→ Recommendation
```

## Candidate Generation
Candidates may come from:
- rule-based financial logic
- spending-pattern analysis
- content-based methods
- future collaborative filtering
- context-aware signal fusion

The LLM should not independently invent a financial action without a supported candidate or evidence path.

## Required Recommendation Metadata

Each recommendation should have:
- category
- action
- rationale
- supporting inputs
- confidence
- risk level
- evidence/source references
- freshness
- policy status

## Suitability Rules

A recommendation should be reconsidered or blocked when:
- critical financial context is missing
- the recommendation conflicts with the user's stated goal
- affordability is unclear
- risk tolerance is unknown for a risk-sensitive action
- source information is stale
- evidence is contradictory
- the model cannot explain the recommendation from available inputs

## Recommendation Ranking

A future scoring model may combine:
- user relevance
- financial suitability
- evidence quality
- freshness
- confidence
- risk
- historical feedback

Safety is a gating condition, not merely another ranking feature.

## No-Guarantee Principle

The system must not represent uncertain financial outcomes as guaranteed.

## Explainability

Every personalized recommendation should answer:
1. What is being recommended?
2. Why is it relevant to this user?
3. Which user data influenced it?
4. Which external evidence influenced it?
5. What uncertainty or limitation exists?
