## Issue tracking workflow (always follow this)

Whenever you identify or are asked to fix a bug, or implement a feature
request that originated from manual testing or user feedback, follow this
workflow automatically — do not wait to be asked each time:

1. **Before fixing**, file a GitHub issue via `gh issue create` with:
   - A clear title describing the symptom (not the fix).
   - A body containing:
     - `## Symptom` — the exact observed behavior (command run, exact
       output), not a paraphrase.
     - `## Diagnosis` — what was ruled out and why, if any investigation
       happened before the fix was clear.
   - Appropriate label (`bug` or `enhancement`).

2. **Implement the fix.**

3. **After fixing**, add a comment to the same issue containing:
   - `## Fix applied` — what changed and why, including whether existing
     logic was reused/consolidated rather than duplicated.
   - `## Verification command` — the exact command the user should run
     themselves against real data to confirm the fix, not just "tests
     pass." If a CLI command or specific UI flow exists that exercises the
     real fix, give that exact command/flow.
   - Any regression tests added, named specifically.

4. **Do not close the issue yourself.** Leave it open and tell the user
   it's ready for their verification. The user closes it after running the
   verification command themselves and confirming it actually works
   against real data — this project has a track record of passing test
   suites missing real bugs that only surfaced under manual testing
   (e.g. flat-directory note discovery, asset-type validation exemption),
   so a human verification step before closing is a deliberate, permanent
   part of this workflow, not a one-off preference.

5. If a fix instruction is sourced from a conversation (rather than your
   own investigation), include the literal instruction text in the issue
   body or comment, not a summary of it — the user uses these issues as a
   reference for what an effective fix-instruction looks like over time.
