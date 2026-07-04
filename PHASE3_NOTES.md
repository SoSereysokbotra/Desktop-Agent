# Phase 3 Notes

Open items surfaced during earlier phases, to be addressed in Phase 3.

## RISK: `open_app` target-cleanliness gap

**Severity: real risk (not a curiosity).** Surfaced by the Phase 2 live sanity
run, where the agent typed `hello` into a pre-existing Notepad tab that already
contained the user's unsaved code, prepending into real content.

**Description:**
`open_app` for notepad (and likely other apps) reuses an existing window/tab if
one is already open, rather than guaranteeing a fresh target. `type_text` has no
awareness of what is already in the target document. Real risk: the agent could
type into pre-existing user content unknowingly, silently corrupting a document.

**Needs either:**
- (a) a "new document" step before typing when a fresh target is required, or
- (b) an observation/confirmation step before typing into an ambiguous target.

**Context:**
This is exactly the class of failure the Phase 2 plan's original
safety/confirmation layer (old "Phase 6") was meant to catch. It should be
folded into Phase 3 rather than deferred, because destructive typing into
existing user content is a data-loss risk, not just a UX rough edge.
