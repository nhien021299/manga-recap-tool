# `gemini_script_service_final_v2.py` Adoption Analysis

## Summary

Recommendation: **adopt selectively**, not as a wholesale file replacement.

The candidate file is a narrow behavioral update to the active backend Gemini service at `ai-backend/app/services/gemini_script_service.py`. It does **not** require API, route, config, provider, or frontend contract changes, but it does change prompt wording and story-memory behavior in ways that should be merged surgically.

Primary conclusion:
- Keep the stronger grounding-oriented prompt wording.
- Keep the descriptor and anti-role-hallucination changes.
- Keep the revised batch summarization approach.
- Reject the `recentNames` persistence change because it increases stale identity carryover risk.
- Reject the Gen Z removal if the project intends to stay aligned with the current M2 roadmap wording.

## Contract And Integration Check

Verified against the active backend entrypoints and schemas:
- Route stays `POST /api/v1/script/generate` in `ai-backend/app/routes/script.py`.
- FastAPI wiring still instantiates `GeminiScriptService` from `ai-backend/app/main.py`.
- Response/domain models remain `ScriptJobResult`, `ScriptGenerationResponse`, `Metrics`, and `StoryMemory` in `ai-backend/app/models/api.py` and `ai-backend/app/models/domain.py`.
- No new settings or provider changes are required in `ai-backend/app/core/config.py` or `ai-backend/app/services/provider_registry.py`.

Conclusion:
- Public API changes: **none**.
- FE-BE contract drift: **none detected**.
- Dependency wiring changes needed to adopt selected pieces: **none**.

Validation:
- `python -m pytest .\ai-backend\tests\test_gemini_script_service.py .\ai-backend\tests\test_routes.py`
- Result: `18 passed`

## Change-By-Change Recommendation

### Prompt language changes

**1. More specific neutral descriptor examples**

Candidate change:
- Replace broad examples like `the man` / `the woman` with more visual descriptors like `the black-clad man` / `the wounded man`.

Recommendation:
- **Keep**.

Reasoning:
- Better aligned with the current M2 direction to avoid flat labels.
- Improves prompt specificity without changing contract or control flow.
- Low hallucination risk because these remain examples, not forced outputs.

**2. Shift naming guidance toward visible, image-grounded traits**

Candidate change:
- Prefer `outfit/weapon/wound/posture/age impression` over `age/role/job`.

Recommendation:
- **Keep**.

Reasoning:
- Stronger grounding in directly visible evidence.
- Lowers the chance that the model overcommits to social role or profession labels.
- Better fits the roadmap emphasis on descriptor continuity and uncertainty control.

**3. Broaden the anti-inference rule to "profession or social role"**

Candidate change:
- Replace the narrower explicit list of jobs with the broader rule `Do not infer a profession or social role unless the current images make that role genuinely clear.`

Recommendation:
- **Keep**.

Reasoning:
- Broader rule is easier for the model to generalize.
- Better anti-hallucination guard than a short example list.
- Low regression risk.

**4. Remove Gen Z phrasing guidance**

Candidate change:
- Remove the rule allowing a very light amount of Vietnamese Gen Z phrasing.

Recommendation:
- **Reject for now**.

Reasoning:
- This is the only prompt change that moves away from the current roadmap wording, which explicitly allows a light Gen Z layer in the M2 prompt update.
- Removing it may improve tone stability, but that is a product-direction decision rather than a clear technical win.
- If the product direction has changed and the team now wants a stricter cinematic tone, this can be revisited later as a separate prompt decision.

### Story memory changes

**5. Increase memory cap from `50/280` to `70/420`**

Candidate change:
- `MAX_MEMORY_WORDS: 50 -> 70`
- `MAX_MEMORY_CHARS: 280 -> 420`

Recommendation:
- **Keep**, but only together with the revised summarization logic.

Reasoning:
- The larger cap gives the new summary format enough room to preserve continuity instead of collapsing back to a single short sentence.
- Measured prompt impact is acceptable. In two representative comparisons, the candidate prompt was still shorter overall because its wording is leaner elsewhere:
- Representative prompt: current `3846`, candidate `3569`, delta `-277`.
- Long-memory prompt: current `4003`, candidate `3866`, delta `-137`.
- Worst-case carryover text can still grow by about `140` characters because the compact summary cap moves from `280` to `420`, so this is a real but bounded token increase.

Risk:
- Mild increase in stale-context anchoring.
- Acceptable if name carryover remains conservative.

**6. Revise `_summarize_batch()` to summarize the last 3 items and prefer first + last sentence**

Candidate change:
- Move from "first sentence of the last 2 items" to "compressed summary over the last 3 items, preferring first + last sentence".

Recommendation:
- **Keep**.

Reasoning:
- This is the strongest quality improvement in the candidate update.
- The current summarizer often preserves only one mid-batch beat.
- The candidate summarizer preserves entry and exit state for the batch, which better supports adjacent-batch continuity.

Observed behavior:
- Current sample summary captured one sentence and lost the setup-to-payoff arc.
- Candidate sample summary preserved both the immediate threat and the final unresolved beat.

Risk:
- Slightly larger memory payload.
- Lower risk than the `recentNames` persistence change because this affects scene continuity more than identity certainty.

**7. Keep prior `recentNames` when the current chunk no longer matches a name**

Candidate change:
- Current behavior drops names after the first chunk if the current chunk does not mention them.
- Candidate behavior retains `previous_memory.recentNames`.

Recommendation:
- **Reject**.

Reasoning:
- This is the highest-risk change in the candidate file.
- It improves continuity in chapters where names temporarily disappear, but it also keeps stale names alive deeper into the prompt.
- Even with the explicit rule that carryover names are not proof, the model can still over-attach to those names when current images are ambiguous.

Observed behavior:
- Current logic returned `[]` in a no-name follow-up chunk.
- Candidate logic returned `['Ly Pham', 'Elder Mo']` for the same chunk.

Conclusion:
- The continuity gain is real, but it conflicts with the project bias toward minimizing identity hallucination risk.
- If this is revisited later, it should be done with a stricter policy than unconditional carryover retention.

## Recommended Merge Shape

Do **not** replace `ai-backend/app/services/gemini_script_service.py` with `gemini_script_service_final_v2.py`.

Recommended surgical merge:
- Keep the updated neutral descriptor examples.
- Keep the updated image-grounded naming guidance.
- Keep the broader `profession or social role` anti-inference rule.
- Keep the revised `_summarize_batch()` implementation.
- Keep the larger memory cap so the revised summary has room to work.
- Do **not** adopt the `recentNames` carryover retention logic.
- Do **not** remove the light Gen Z phrasing guidance unless product direction explicitly changes.

## Test And Validation Follow-Up

Service tests that should change only if the selective merge is implemented:
- Update `_build_unified_prompt()` assertions only for the prompt lines that were intentionally kept.
- Keep the current assertion around Gen Z wording if the removal is rejected.
- Add a targeted regression test for `_summarize_batch()` to confirm the new multi-sentence summary shape.
- Add a targeted regression test proving `_extract_recent_names()` still drops stale names when the current chunk provides no match.

Contract checks that should remain unchanged after selective adoption:
- `generate_script()` result shape.
- `Metrics` fields.
- `StoryMemory` schema.
- Route behavior for `/api/v1/script/generate`.

## Final Decision

Decision: **adopt selectively**.

Why:
- The candidate prompt improvements are mostly stronger and safer than the current wording.
- The candidate summary logic is a meaningful continuity improvement.
- The candidate `recentNames` persistence is too permissive for the current identity-safety posture.
- The Gen Z removal is a product-direction change, not a clear technical fix, and currently conflicts with the roadmap language.
