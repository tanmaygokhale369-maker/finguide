# FinGuide+ — AI Evaluation Framework

## Objective
Move beyond qualitative recommendation evaluation and establish measurable evidence of system quality.

## Evaluation Areas

### 1. Extraction
Metrics:
- precision
- recall
- F1
- numeric extraction accuracy
- entity/field accuracy

### 2. Validation
Measure:
- invalid-value detection
- contradiction detection
- low-confidence detection
- false acceptance rate

### 3. Context Completeness
Measure:
- missing-critical-context detection
- unnecessary clarification rate
- recommendation blocking accuracy

### 4. Grounding
Measure:
- factual accuracy
- source attribution accuracy
- unsupported-claim rate
- citation/source correctness

### 5. Recommendation Quality
Evaluate:
- relevance
- suitability
- consistency
- usefulness
- explanation quality
- uncertainty calibration

### 6. Safety
Measure:
- unsafe recommendation rate
- policy violation rate
- hallucination rate
- prompt-injection resistance
- stale-data handling
- inappropriate certainty

### 7. Human Evaluation

Use structured review by knowledgeable evaluators for:
- recommendation suitability
- explanation quality
- financial safety
- factual grounding

The existing blueprint identifies the lack of a labeled "correct recommendation" dataset. This framework should therefore combine rule-based tests, synthetic scenarios, curated cases and expert/human evaluation rather than assuming a single ground-truth label.

## Regression Suite

Maintain fixed scenarios covering:
- normal users
- incomplete profiles
- contradictory inputs
- unusual values
- high-debt situations
- stale market data
- conflicting sources
- malicious/prompt-injection content
- ambiguous financial language

Every model/prompt/policy change should be evaluated against the regression suite.

## Monitoring

Track over time:
- recommendation acceptance
- rejection
- user corrections
- safety blocks
- clarification frequency
- source failures
- model failures
- recommendation drift

User acceptance is a feedback signal, not proof of financial correctness.
