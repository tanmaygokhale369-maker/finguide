# FinGuide+ — Brick-by-Brick Implementation Plan
## AI Build Context Document

**Purpose:** This document is the implementation guide for building FinGuide+ incrementally.  
**Primary rule:** Build one brick at a time, verify it, then move to the next brick. Do not prematurely implement future features.

---

## 1. Product Context

FinGuide+ is a text-augmented personal finance recommendation system using web/social-media analytics.

Core foundation:
- React frontend
- FastAPI backend
- PostgreSQL database
- SQLAlchemy + Alembic
- Pydantic v2
- Versioned REST API: `/api/v1/`
- Rule-based chatbot initially
- Separate `ai/` module
- `ChatbotEngine` interface so an LLM can later replace the rule-based engine

Future AI capabilities:
- LLM conversational AI
- Financial profiling
- Expense categorization
- Spending-pattern analysis
- Recommendation engine
- Financial sentiment analysis / FinBERT
- Summarization
- Context-aware recommendations
- Explainable AI using SHAP/LIME
- Financial news and market data
- External web/social data

---

# 2. Non-Negotiable Architecture

Never allow an AI generation model to directly produce the final financial recommendation shown to a user.

Required logical flow:

`User Input`
→ `Data Extraction`
→ `Confidence + Validation`
→ `Financial Context Completeness Check`
→ `User Financial Profile`
→ `Spending Analysis`
→ `Candidate Recommendation Generation`
→ `Evidence Retrieval`
→ `Source Trust + Freshness Validation`
→ `Suitability Validation`
→ `Safety & Policy Gate`
→ `Fact/Grounding Verification`
→ `Explainable Recommendation + Sources`
→ `User Feedback`
→ `Evaluation + Personalization`

### Deterministic vs AI responsibility

AI components may extract, classify, summarize, interpret, and generate candidate recommendations or explanations.

The application/backend must remain authoritative for:
- authentication and authorization
- financial data validation
- deterministic financial calculations
- context completeness checks
- suitability and safety rules
- evidence/source verification
- recommendation approval
- database integrity
- auditability and provenance

The LLM must never be the sole authority for a critical financial calculation, policy decision, authorization decision, or final recommendation approval.

The system must be able to:
- ask for missing information
- detect contradictory financial information
- express uncertainty
- reject unsafe recommendations
- verify factual financial claims
- detect stale external data
- track sources and timestamps
- collect user feedback
- evaluate recommendation quality

---

# 3. Implementation Strategy

Build strictly in this order:

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
13. Safety & Suitability Layer
14. Explainability
15. External Financial Data
16. News + Sentiment
17. Context-Aware Recommendations
18. Feedback + Evaluation
19. Authentication + Security Hardening
20. Production Readiness

### Recommendation lifecycle

Every recommendation candidate follows a traceable lifecycle:

```text
CANDIDATE
   ↓
VALIDATED
   ↓
APPROVED / MODIFIED / BLOCKED / CLARIFY / ESCALATE
   ↓
PRESENTED
   ↓
ACCEPTED / REJECTED / IGNORED
   ↓
EVALUATED
```

Each state transition should be auditable and tied to the applicable policy/model/evidence versions.

Each brick must have:
- Objective
- Prerequisites
- Files/folders
- Database changes
- API contracts
- AI components
- Input/output contracts
- Tests
- Definition of Done
- Explicit non-goals

---

# 4. Brick Specifications

## Brick 01 — Repository & Environment

### Objective
Create a clean monorepo structure and reproducible development environment.

### Structure
```text
finguide/
├── frontend/
├── backend/
├── docs/
├── tests/
├── .env.example
├── README.md
└── docker-compose.yml
```

Backend should contain:
```text
backend/
├── app/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── ai/
│   └── main.py
└── tests/
```

### Definition of Done
- Project installs cleanly
- Frontend starts
- Backend starts
- Environment variables are documented
- No secrets committed
- Basic health check works

### Do Not Implement
- LLM
- recommendations
- authentication
- external APIs

---

## Brick 02 — React Foundation

### Objective
Build the basic frontend shell.

### Initial screens
- Dashboard
- Financial Profile
- Transactions
- Chat
- Recommendations
- Settings

### Definition of Done
- React app runs
- Routing works
- API service layer exists
- Common layout/components exist
- Loading/error states exist

---

## Brick 03 — FastAPI Foundation

### Objective
Create the backend API architecture.

### Requirements
- `/api/v1/`
- configuration management
- Pydantic schemas
- exception handling
- logging
- health endpoint
- CORS configuration

### Initial endpoints
```text
GET /api/v1/health
```

### Definition of Done
- API starts reliably
- OpenAPI documentation works
- Versioning is established
- Validation errors are structured

---

## Brick 04 — PostgreSQL + SQLAlchemy

### Objective
Create the persistent data layer.

### Initial entities
- User
- FinancialProfile
- Transaction

### Requirements
- SQLAlchemy
- Alembic
- numeric financial fields
- timestamps
- indexes where appropriate
- migrations

### Definition of Done
- Database connects
- Migration creates schema
- CRUD operations tested
- Monetary values are not stored as floating-point numbers

---

## Brick 05 — User/Profile APIs

### Objective
Create APIs for storing and retrieving financial profile information.

### Example profile fields
- income
- fixed expenses
- variable expenses
- savings
- debt
- financial goals
- dependents
- emergency-fund information
- insurance information
- investment information

### Identity architecture

All profile APIs must depend on an application-level user-context abstraction rather than trusting a client-supplied `user_id`.

During prototype development this may use a controlled development user context. Brick 19 replaces the implementation with authenticated identity from the session/token without changing the service contract.

### Rule
Do not assume missing information is zero.

### Definition of Done
- Profile can be created/updated/retrieved
- Validation works
- Missing values remain explicitly missing
- API contracts are documented

---

## Brick 06 — Chatbot Foundation

### Objective
Create a chatbot interface that can support both rule-based and LLM implementations.

### Architecture
```text
Chat API
   ↓
ChatbotEngine interface
   ├── RuleBasedChatbot
   └── Future LLMChatbot
```

### Rule
The chatbot must not bypass validation, safety, or recommendation policy.

### Definition of Done
- Chat endpoint exists
- Engine interface exists
- Rule-based implementation works
- Conversation context is controlled
- LLM can later replace the implementation without changing the API contract

---

## Brick 07 — Financial Data Extraction

### Objective
Extract structured financial information from natural-language user input.

### Example
Input:
> "I earn 60,000 a month, spend around 25,000 and have a 5 lakh loan."

Output:
```json
{
  "income": 60000,
  "expenses": 25000,
  "debt": 500000
}
```

### Required metadata
Every extracted field should support:
- value
- source text
- confidence
- extraction method
- timestamp

### Definition of Done
- Common financial entities are extracted
- Confidence is attached
- Ambiguous values are flagged
- Extraction does not silently invent values

---

## Brick 08 — Data Validation & Confidence

### Objective
Validate extracted and stored financial information before AI uses it.

### Required statuses
```text
VALID
LOW_CONFIDENCE
CONFLICTING
INCOMPLETE
REQUIRES_CLARIFICATION
REJECTED
```

### Checks
- type validation
- range validation
- impossible values
- contradictory values
- duplicate information
- temporal consistency
- missing critical information

### Example
If user says:
- income = ₹50,000
- later income = ₹80,000

Do not silently choose one. Mark the conflict and clarify.

### Definition of Done
- Every important financial input can be validated
- Contradictions are detectable
- Confidence thresholds are configurable
- Invalid data cannot directly drive recommendations

---

## Brick 09 — Financial Profile

### Objective
Transform validated financial data into a structured user profile.

### Possible derived metrics
- savings ratio
- debt-to-income ratio
- expense-to-income ratio
- emergency-fund coverage
- liquidity indicators

### Financial Calculation Engine

Deterministic financial metrics must be produced by application code, not by an LLM.

Each derived metric should retain:
- metric name
- value
- formula/calculation definition
- input values or input references
- calculation version
- calculated_at

### ML
K-Means may later be used for financial profiling/segmentation.

### Rule
Derived metrics must retain their input data and calculation definition.

### Definition of Done
- Profile generated from validated data
- Derived metrics reproducible
- Profile versioning supported
- Missing inputs are clearly represented

---

## Brick 10 — Transaction System

### Objective
Support manual transaction entry.

### Transaction fields
- amount
- type
- category
- date
- description
- source
- confidence where AI categorization is involved

### Categories
Use a controlled category taxonomy.

### Future
- CSV import
- bank integration
- Account Aggregator

### Definition of Done
- Create/read/update/delete works
- Transactions are user-scoped
- Monetary calculations are accurate
- Categories are validated

---

## Brick 11 — Spending Analysis

### Objective
Identify spending patterns from transactions.

### Initial analysis
- category totals
- monthly totals
- income vs expenses
- recurring expenses
- unusual spending
- trend detection

### Rule
Patterns are observations, not automatic financial advice.

### Definition of Done
- Analysis reproducible
- Date ranges explicit
- Missing transaction data acknowledged
- Calculations tested

---

## Brick 12 — Recommendation Engine

### Objective
Generate candidate financial recommendations using validated profile, spending patterns, goals, and trusted evidence.

### Recommendation object
```text
recommendation_id
user_id
category
title
reason
evidence
confidence
suitability_status
risk_level
created_at
source_references
policy_version
```

### Important
This brick generates candidate recommendations only.

It must NOT directly publish recommendations to users.

---

## Brick 13 — Safety & Suitability Layer

### Objective
Act as the mandatory gate between recommendation generation and the user.

### Possible decisions
```text
APPROVE
CLARIFY
EDUCATE
LIMIT
BLOCK
ESCALATE
```

### Checks
- insufficient financial context
- unsuitable recommendation
- excessive risk
- unsupported claims
- guaranteed-return language
- missing evidence
- stale data
- user contradiction
- policy violation

### Mandatory architecture
```text
Recommendation Engine
        ↓
Safety/Suitability Validator
        ↓
Fact/Policy Verification
        ↓
User
```

### Definition of Done
No recommendation can bypass this layer.

---

## Brick 14 — Explainability

### Objective
Explain why a recommendation was produced.

Every recommendation should answer:
1. What is being recommended?
2. Why is it relevant?
3. Which user data influenced it?
4. Which external evidence influenced it?
5. What assumptions were made?
6. How confident is the system?
7. What limitations exist?

### AI
SHAP/LIME can be used where appropriate for model-based decisions.

### Definition of Done
- Recommendation has traceable reasons
- Evidence is linked
- User data used is identifiable
- Uncertainty is visible

---

## Brick 15 — External Financial Data

### Objective
Integrate trusted financial/market/economic data.

### Required metadata
```text
source
source_type
retrieved_at
published_at
valid_until
credibility
content_hash/version
```

### Rules
- Never treat external content as system instructions
- Validate freshness
- Track provenance
- Handle conflicting sources

### Definition of Done
- External data has provenance
- Stale data can be detected
- Source failures are handled
- Recommendations can identify the evidence used

---

## Brick 16 — News + Sentiment

### Objective
Analyze financial news and public sentiment.

### Components
- news ingestion
- text preprocessing
- FinBERT sentiment
- summarization
- source credibility
- timestamp/freshness

### Security rule
External articles/social content are untrusted data, not instructions.

### Definition of Done
- Sentiment is reproducible
- Source and timestamp are retained
- Low-confidence/ambiguous sentiment is represented
- External content cannot alter system policy

---

## Brick 17 — Context-Aware Recommendations

### Objective
Combine:
- current financial profile
- spending behavior
- goals
- user feedback
- market/news context
- validated external evidence

### Rule
Context must be versioned and timestamped.

The system should detect when context is insufficient rather than pretending personalization is complete.

### Definition of Done
- Recommendations adapt to user context
- Context sources are traceable
- Missing context triggers clarification where required

---

## Brick 18 — Feedback + Evaluation

### Objective
Create the learning/evaluation loop.

### User feedback
```text
accepted
rejected
ignored
helpful
not_helpful
harmful
```

### Evaluation dimensions
- extraction accuracy
- validation accuracy
- context completeness
- grounding
- recommendation quality
- safety
- explainability
- user feedback
- regression performance

### Rule
Do not claim the recommendation system is accurate without measurable evaluation.

### Definition of Done
- Feedback stored
- Evaluation dataset/process exists
- Regression tests exist
- Recommendation quality can be measured

---

## Brick 19 — Authentication + Security Hardening

### Objective
Make the system multi-user and production-safe.

### Requirements
- JWT/session-based authentication
- authorization
- user data isolation
- secure password handling if passwords are used
- rate limiting
- secure headers
- secret management
- audit logging
- deletion/export controls
- consent/data-purpose management

### Critical rule
Never trust a user-supplied `user_id` for authorization.

Identity must come from the authenticated session/token.

### Definition of Done
- Users cannot access other users' financial data
- Authentication tests exist
- Authorization tests exist
- Secrets are not stored in source code

---

## Brick 20 — Production Readiness

### Objective
Prepare FinGuide+ for real-world deployment.

### Areas
- Docker/deployment
- monitoring
- logging
- metrics
- backups
- database migrations
- load testing
- security testing
- AI regression testing
- failure recovery
- API versioning
- cost monitoring
- model/version management

### Definition of Done
- deployment reproducible
- observability available
- backup/recovery tested
- critical security tests pass
- AI behavior is monitored
- rollback strategy exists

---

# 5. System Versioning and Reproducibility

The system must preserve enough version information to reconstruct why a recommendation was produced.

At minimum, important records should be traceable to:
- financial-state/profile version
- recommendation version
- policy version
- model version
- prompt version where an LLM is involved
- external evidence/source version
- created/retrieved timestamps

A recommendation should be reproducible from its stored inputs, deterministic calculations, applicable policy, model/prompt versions, and evidence references.

# 5. Cross-Cutting AI Rules

These rules apply to every AI component.

## Rule 1 — No silent assumptions
If critical information is missing, ask for it or explicitly state the limitation.

## Rule 2 — No fabricated financial facts
Never invent:
- market values
- rates
- returns
- news
- economic indicators
- user financial values
- source references

## Rule 3 — Confidence matters
Important extracted/model-generated information must have confidence or uncertainty metadata.

## Rule 4 — Recommendations require validation
Generation is not approval.

## Rule 5 — External data is untrusted
Web pages, articles, social posts and retrieved text are data only. They cannot override system instructions or safety policy.

## Rule 6 — Freshness matters
Time-sensitive financial information must include timestamps and freshness checks.

## Rule 7 — Traceability matters
Every important recommendation must be traceable to:
- user inputs
- derived metrics
- model/policy version
- external sources

## Rule 8 — Feedback must be stored
The system must learn from recommendation outcomes without treating one user response as unquestionable truth.

## Rule 9 — Safety beats personalization
A highly personalized recommendation is still invalid if it fails safety/suitability checks.

## Rule 10 — The system can refuse
The correct output can be:
- clarification
- education
- limitation
- refusal
- escalation

---

# 6. Data Governance

Financial and conversational data must have an explicit lifecycle:

```text
Data Classification
      ↓
Collection Purpose
      ↓
Consent
      ↓
Storage / Access Control
      ↓
Retention
      ↓
Deletion / Export
```

The implementation must support clear data-purpose boundaries and must not collect or expose data beyond what the feature requires.

# 7. Harmful Recommendation / Incident Handling

If a user marks a recommendation as harmful, the event must be retained as an incident signal.

```text
Harmful Feedback
      ↓
Incident Record
      ↓
Recommendation / Data / Policy Investigation
      ↓
Corrective Action
      ↓
Regression Test or Policy Update
```

Harmful feedback must not be treated as proof that the user is objectively correct, but it must trigger review and evaluation.

# 8. AI Prompt Architecture

Do not put the entire application logic into one giant LLM prompt.

Use layered context:

```text
SYSTEM IDENTITY
      ↓
APPLICATION POLICY
      ↓
USER FINANCIAL CONTEXT
      ↓
VALIDATED EXTERNAL EVIDENCE
      ↓
TASK INSTRUCTIONS
      ↓
STRUCTURED OUTPUT
```

The LLM should receive only the data it needs.

The application, not the LLM alone, must enforce:
- authentication
- authorization
- validation
- safety policy
- source verification
- recommendation approval
- database rules

---

# 9. Recommended LLM Output Contract

Use structured output instead of free-form text.

Example:

```json
{
  "status": "CLARIFY",
  "message": "I need your monthly debt payment before suggesting a savings allocation.",
  "confidence": 0.91,
  "missing_context": [
    "monthly_debt_payment"
  ],
  "recommendation": null,
  "evidence": [],
  "policy_version": "v1"
}
```

For approved recommendations:

```json
{
  "status": "APPROVE",
  "recommendation": {
    "title": "...",
    "reason": "...",
    "confidence": 0.86,
    "risk_level": "LOW"
  },
  "evidence": [
    {
      "source": "...",
      "retrieved_at": "...",
      "published_at": "..."
    }
  ],
  "assumptions": [],
  "limitations": [],
  "policy_version": "v1"
}
```

---

# 10. Development Rules for AI Coding Agents

When an AI coding agent is used to build FinGuide+:

1. Read this document before modifying the project.
2. Determine the current completed brick.
3. Implement only the next required brick unless explicitly instructed otherwise.
4. Inspect the existing code before creating new files.
5. Reuse existing architecture instead of duplicating services.
6. Do not change API contracts without explaining the impact.
7. Do not add future features prematurely.
8. Add tests with every meaningful feature.
9. Keep business logic separate from routes/controllers.
10. Keep AI logic inside the `ai/` or dedicated service layer.
11. Keep financial calculations deterministic and testable.
12. Never place secrets in code.
13. Never bypass authentication/authorization when it exists.
14. Never let generated AI text directly become an approved recommendation.
15. Preserve provenance and timestamps for external evidence.
16. Make failures explicit rather than silently using fallback assumptions.
17. Update documentation when architecture changes.
18. Run tests before declaring a brick complete.
19. State exactly what was implemented.
20. State what remains intentionally unimplemented.

---

# 11. Definition of Done — Universal Checklist

A brick is complete only when:

- [ ] Objective implemented
- [ ] Existing architecture preserved
- [ ] Required files created/updated
- [ ] Database migrations completed if required
- [ ] API contracts defined
- [ ] Validation implemented
- [ ] Error handling implemented
- [ ] Tests added
- [ ] Tests pass
- [ ] Security implications reviewed
- [ ] AI safety implications reviewed
- [ ] Documentation updated
- [ ] No future brick was accidentally implemented
- [ ] Definition of Done satisfied

---

# 12. Current Priority

Build the foundation first.

Recommended immediate sequence:

```text
01 Repository
   ↓
02 React
   ↓
03 FastAPI
   ↓
04 PostgreSQL
   ↓
05 User/Profile
   ↓
06 Chatbot
   ↓
07 Extraction
   ↓
08 Validation
```

Do not jump directly to LLM recommendations.

The strongest architecture is:

`Reliable Data → Validated Context → Analysis → Recommendation → Safety → Evidence → Explanation → Feedback`

---

# 13. Core Product Principle

FinGuide+ should not be designed merely as an AI that gives financial answers.

It should be designed as a **validated, evidence-aware, safety-gated personal finance decision-support system**.

The AI generates and interprets information, but the surrounding system controls:
- what data is trusted
- what context is sufficient
- what recommendations are allowed
- what evidence supports them
- how uncertainty is communicated
- how outcomes are evaluated

**Implementation principle:**

`Generate → Validate → Verify → Guard → Explain → Feedback → Evaluate`

This principle must remain intact as the system evolves.
