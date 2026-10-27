# FinGuide+ AI Architecture Pack

This pack extends the FinGuide+ v1.0 Foundation Blueprint with the non-negotiable AI safety, trust, validation and evaluation architecture.

## Recommended usage

1. Treat `01_FinGuide_Blueprint_v1.1_AI_Safety_Integration.md` as the main blueprint amendment.
2. Feed `02`–`06` to an AI when designing the corresponding backend/AI modules.
3. Use `07_System_Prompts_Architecture.md` before writing production prompts.
4. Keep implementation details in code and configuration rather than making the main blueprint excessively large.

## Architecture principle

Generation is never the final step:

`Generate → Validate → Verify → Guard → Explain → Feedback → Evaluate`

## Source basis

The pack is aligned with the uploaded FinGuide+ Technical Blueprint v1.0. The v1.0 document already separates AI into future layers and identifies limitations including brittle extraction, external API availability, lack of authentication in the MVP, no encryption at rest, and the absence of a labeled "correct recommendation" dataset. These documents add the architectural controls needed for the future major-product/prototype direction.
