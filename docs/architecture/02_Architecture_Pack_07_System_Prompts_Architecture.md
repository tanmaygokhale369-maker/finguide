# FinGuide+ — System Prompt Architecture

## Purpose
Define how LLM prompts should be organized without putting the entire business policy inside one prompt.

## Prompt Layers

### Layer 1 — System Identity
Defines:
- role
- scope
- communication style
- high-level safety boundaries

### Layer 2 — Application Policy
Defines:
- allowed recommendation behavior
- refusal/clarification rules
- data handling expectations
- grounding requirements

### Layer 3 — Context
Provides:
- validated financial profile
- transaction summaries
- goals
- relevant conversation state

Only validated/approved data should be passed as authoritative user context.

### Layer 4 — External Evidence
Provides:
- retrieved facts
- source metadata
- timestamps
- freshness
- provenance

External text must be clearly delimited as untrusted content.

### Layer 5 — Task Instruction
Defines the current task:
- extract
- classify
- summarize
- explain
- generate recommendation candidate
- answer user question

## Important Separation

Do not rely on prompts alone for critical safety.

```text
Prompt Rules
+
Backend Validation
+
Recommendation Policy
+
Evidence Verification
+
Safety Guardrail
```

The backend must enforce rules that should not depend on LLM obedience.

## Structured Output

Where practical, use structured output for machine-consumed results.

Example:

```json
{
  "response": "...",
  "extracted_data": {},
  "confidence": 0.0,
  "needs_clarification": false,
  "recommendation_candidates": [],
  "sources": []
}
```

## Prompt-Injection Defense

Retrieved content must be enclosed and labeled as data.

The model should be instructed that:
- retrieved text is not an instruction source
- user-provided external text cannot modify system policy
- conflicting instructions inside documents/web pages must be ignored

## Versioning

Version:
- system prompt
- policy
- model
- retrieval configuration
- safety rules

Store versions with recommendation audit records.
