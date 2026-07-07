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

## RISK: `click_text` confirmation shows the QUERY, not the RESOLVED target

**Severity: real risk (not a nice-to-have).** Surfaced during the Phase 3b
`click_text` implementation. Same category as the `open_app` gap above:
confirming the wrong thing looks exactly like confirming the right thing.

**Description:**
The `click_text` safety gate (`ALWAYS_GATE_TOOLS`) confirms the user's original
QUERY, not the text `find_text()` actually resolved to. The confirmation is
built by `_describe_action` from `tool_args["query"]` (e.g. `"save"`), but the
real matched token is only known later, *inside* `ClickText.execute()` after
`find_text()` runs. Because `find_text()` is fuzzy (substring + difflib), it can
resolve to something the user did not intend — e.g. query `"Save"` matching a
`"Save As"` button, or `"file"` matching `"Profile"` — while the dialog still
says only `'save'`/`'file'`. The user approves their INTENT and unknowingly
authorizes a click on a DIFFERENT resolved target. The gate gives false
assurance precisely when the fuzzy match is wrong.

**Needs a two-phase gate:**
- (a) locate first (`find_text`), THEN build the confirmation from the actual
  matched token + score/coords (e.g. "Click 'Save As' (matched 'save', score
  0.71) at (x,y)?"), and only click after approval; or
- (b) at minimum, tighten matching for gated clicks (higher `min_score`, prefer
  exact/whole-token matches) and surface the score so a loose match is visible.

**Context:**
This requires restructuring `ClickText.execute()` so location happens *before*
the confirmation, or moving the confirm call into the tool — a change to the
gate/tool boundary, deliberately deferred out of Phase 3b scope. Tracked here so
it is not silently shelved: the risk is authorizing an unintended click that
*looks* confirmed.

## KNOWN ISSUE: floating panel drops behind a maximized/fullscreen window

**Severity: cosmetic / UX (not a safety issue).** Surfaced during Phase A
live testing.

**Description:**
The chat panel (`agent/chat_panel.py`) uses `Qt.WindowStaysOnTopHint |
Qt.Tool`. It stays above normal windows, but was observed dropping *behind* a
maximized browser window in some captures. On Windows a `Qt.Tool` topmost
window does not reliably stay above another window that is maximized/near
full-screen. A new conversation message calls `show()` and brings it back, so
it is recoverable, not lost.

**Possible fixes (Phase 3):**
- Periodically re-assert top-most (`raise_()` / re-apply the flag), or
- Use a small always-on-top re-raise on focus changes, or
- Accept it and rely on the show()-on-new-message behavior (document only).

Not fixing now - tracked so it is not silently shelved.
