# Phase 2 Readiness Check - ReAct Loop Dependency Analysis

## Phase 2 Overview (from original plan)

**Phase 2 — ReAct Reasoning Loop:**
- Build an orchestrator that loops: Think -> Act -> Observe -> Think again
- Add observation/verification step after every action
- Log each loop iteration to memory.db
- Continue up to max_steps limit until LLM declares goal complete

## Dependency Analysis

### Does Phase 2 depend on JSON-output reliability?

**YES - Critical dependency identified:**

```python
# Phase 2 Think step will need structured output like:
{
  "thought": "User wants to wait, I need the wait tool",
  "tool": "wait",
  "args": {"seconds": 5},
  "goal_complete": false,
  "next_step": "observe the wait result"
}

# Or at minimum:
{
  "continue": true,
  "action": "wait",
  "args": {"seconds": 5}
}
```

### Current Model Performance

**Phase 1 Test Result:**
- Simple command: `"please wait for 3 seconds"`
- Expected: `{"tool": "wait", "args": {"seconds": 3}}`
- **Actual**: Hallucinated text, wrong tool, chat leakage
- **Success rate**: ~0%

**Implication for Phase 2:**
If the model can't produce simple tool JSON (1 field, 1 nested object), it **cannot** handle Think-step JSON (multiple fields, reasoning text, boolean flags).

### Phase 2 Failure Modes Without Fix

1. **Think step returns malformed JSON**
   - Parser fails → loop exits early
   - User sees: "I couldn't understand that command: Expecting value..."
   - Task incomplete, no retry

2. **Think step hallucinates wrong action**
   - Model chooses wrong tool or wrong args
   - Observer sees failure, but Think step doubles down on wrong approach
   - Infinite loop or wrong outcome

3. **Think step can't decide when to stop**
   - `goal_complete` field always false → max_steps hit
   - Or always true → exits after first step regardless of outcome

4. **Think step leaks into conversation**
   - Starts generating fake user responses
   - Breaks the ReAct format completely

---

## Decision Point

### Path A: Phase 1.5 First (Prompt Hardening)
**Timeline**: 1-2 hours
**Then**: Re-test, decide if Phase 2 is safe

**Pros**:
- Quick to try
- May be sufficient for simple Think steps
- Learn what works for Phase 2 prompting

**Cons**:
- May waste time if it doesn't work
- Phase 2 will still be fragile

### Path B: Phase 7 Next (Model Upgrade)
**Timeline**: 3-4 hours
**Then**: Phase 2 with reliable structured output

**Pros**:
- Solves the problem properly
- Makes Phase 2-6 development smoother
- More ambitious features possible (multi-step reasoning, self-correction)

**Cons**:
- More setup time upfront
- Changes dependency management (Ollama/llama.cpp or cloud API)

### Path C: Redesign Phase 2 (Regex-Based State Machine)
**Timeline**: 2-3 hours
**Then**: Phase 2 without LLM Think step

**Approach**:
- Use regex to detect goal completion (e.g., "done", "finished", error patterns)
- Fixed max_steps loop with heuristic stopping conditions
- Observer checks tool result status, not LLM decision
- Think step becomes logged narrative, not decision-making

**Pros**:
- Works with current model
- Deterministic loop behavior
- Fast execution

**Cons**:
- Not truly "agentic" reasoning
- Can't adapt to unexpected situations
- Limits Phase 5 (self-correction) potential

---

## Recommendation

**Ask user to choose:**

1. **Try Phase 1.5** (1 hour) → if it works, proceed to Phase 2; if not, do Phase 7
2. **Skip to Phase 7** (4 hours) → then robust Phase 2 development
3. **Redesign Phase 2** (3 hours) → regex-based, deterministic loop

**My recommendation**: **Option 2 (Skip to Phase 7)**

**Reasoning**:
- Phase 1.5 is unlikely to achieve >70% success with 0.5B model
- Phase 2-6 all benefit from better structured output (ReAct, grounded vision, reflection)
- Time saved on debugging Phase 2 failures > time spent on model upgrade
- Sets up for more ambitious Phase 5-6 features

**Quick win option within Phase 7**:
- Just upgrade to Qwen2.5-1.5B-Instruct (still local, CPU-friendly)
- Test with `test_llm_fallback_detailed.py`
- If still failing, proceed to 7B or cloud option
