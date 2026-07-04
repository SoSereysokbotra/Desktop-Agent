"""
ReAct Orchestrator - Phase 2

Implements a Think -> Act -> Observe reasoning loop on top of the existing
Phase 1 pieces (LLM, Executor, tool registry). The loop runs until the model
declares the goal complete (a "done" action), an unrecoverable parse failure
occurs, or max_steps is reached.

Design notes:
  - Think:   one LLM call that, given the goal + full history, chooses the
             SINGLE next action as JSON, or emits the "done" sentinel tool.
  - Act:     delegates to executor.execute(tool, args) - executor is untouched.
  - Observe: the ToolResult (status + message) is appended to history and fed
             back into the next Think call, which is what enables the model to
             notice a failed action and adjust.
  - Parse failures get ONE retry with a corrective re-prompt; the loop only
    aborts if the model returns invalid JSON twice in a row.
  - Every Think iteration (including parse-error attempts) is logged to the
    task_steps table via memory.log_task_step().
"""

import json
import logging
import re
import time
import uuid

from agent.tools import ToolRegistry

logger = logging.getLogger(__name__)

# Sentinel tool name the model emits when it judges the goal complete.
DONE_TOOL = "done"
# Marker logged to task_steps when a Think call produced unparseable JSON.
PARSE_ERROR_MARKER = "__parse_error__"

CORRECTION_NOTE = (
    "IMPORTANT: Your last response was not valid JSON and could not be parsed. "
    "Respond with ONLY a single valid JSON object and nothing else."
)


class ReActOrchestrator:
    def __init__(self, llm, executor, memory, max_steps=5):
        """
        Args:
            llm: LLM instance exposing generate(prompt, max_tokens=...).
            executor: Executor instance exposing execute(tool, args) -> ToolResult.
            memory: Memory instance exposing log_task_step(...).
            max_steps: Max number of Think iterations before giving up.
        """
        self.llm = llm
        self.executor = executor
        self.memory = memory
        self.max_steps = max_steps

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, goal):
        """
        Run the ReAct loop for a goal.

        Returns a summary dict:
            {
              "task_id", "goal", "status": completed|incomplete|failed,
              "completed": bool, "actions_taken": int, "iterations": int,
              "elapsed_sec": float, "trace": [ {step, thought, tool, args,
              status, observation} ... ], "reason": str
            }
        """
        task_id = uuid.uuid4().hex[:12]
        history = []          # feeds the Think prompt
        trace = []            # returned to caller for inspection
        actions_taken = 0
        consecutive_parse_failures = 0
        succeeded_actions = set()  # (tool, args) pairs that already succeeded
        start = time.perf_counter()

        logger.info(f"[{task_id}] Starting ReAct loop for goal: {goal!r}")

        for step in range(1, self.max_steps + 1):
            # ---- THINK (with one parse retry) ----
            need_correction = consecutive_parse_failures > 0
            raw = self._think(goal, history, correction=need_correction)
            parsed = self._parse_action(raw)

            if parsed is None:
                # Log the failed attempt, then decide retry vs. abort.
                consecutive_parse_failures += 1
                logger.warning(
                    f"[{task_id}] step {step}: unparseable JSON "
                    f"(failure #{consecutive_parse_failures}): {raw[:150]!r}"
                )
                self.memory.log_task_step(
                    task_id, step, goal,
                    thought="(unparseable LLM response)",
                    tool=PARSE_ERROR_MARKER, args={},
                    status="error", observation=raw[:500],
                )
                trace.append({
                    "step": step, "thought": "(unparseable LLM response)",
                    "tool": PARSE_ERROR_MARKER, "args": {},
                    "status": "error", "observation": raw[:200],
                })
                if consecutive_parse_failures >= 2:
                    return self._summary(
                        task_id, goal, "failed", False, actions_taken,
                        step, start, trace,
                        reason="LLM returned invalid JSON twice in a row",
                    )
                # else: loop again for the single retry (does not consume an
                # action; the corrective note is added on the next Think).
                continue

            consecutive_parse_failures = 0
            thought = parsed.get("thought", "")
            tool = parsed.get("tool", "")
            args = parsed.get("args", {}) or {}

            # ---- DONE sentinel ----
            if tool == DONE_TOOL:
                logger.info(f"[{task_id}] step {step}: model reports goal complete")
                self.memory.log_task_step(
                    task_id, step, goal, thought, DONE_TOOL, {},
                    status="success", observation="Goal reported complete",
                )
                trace.append({
                    "step": step, "thought": thought, "tool": DONE_TOOL,
                    "args": {}, "status": "success",
                    "observation": "Goal reported complete",
                })
                return self._summary(
                    task_id, goal, "completed", True, actions_taken,
                    step, start, trace, reason="Model emitted 'done'",
                )

            # ---- Redundant-action guard (deterministic completion backstop) ----
            # If the model re-proposes an action that already SUCCEEDED, the
            # goal is almost certainly met and it is looping. Treat the repeat
            # as an implicit "done" and stop, rather than burning steps.
            action_key = self._action_key(tool, args)
            if action_key in succeeded_actions:
                observation = (
                    f"Implicit done: model re-proposed already-successful action "
                    f"{tool}({json.dumps(args)}); stopping to avoid redundant repetition."
                )
                logger.info(f"[{task_id}] step {step}: {observation}")
                self.memory.log_task_step(
                    task_id, step, goal, thought, DONE_TOOL, {},
                    status="success", observation=observation,
                )
                trace.append({
                    "step": step, "thought": thought, "tool": DONE_TOOL,
                    "args": {}, "status": "success", "observation": observation,
                })
                return self._summary(
                    task_id, goal, "completed", True, actions_taken,
                    step, start, trace,
                    reason="Redundant repeat of a completed action treated as done",
                )

            # ---- ACT ----
            logger.info(f"[{task_id}] step {step}: ACT {tool}({args})")
            result = self.executor.execute(tool, args)
            actions_taken += 1

            # ---- OBSERVE ----
            observation = result.result
            entry = {
                "step": step, "thought": thought, "tool": tool, "args": args,
                "status": result.status, "observation": observation,
            }
            history.append(entry)
            trace.append(entry)
            self.memory.log_task_step(
                task_id, step, goal, thought, tool, args,
                result.status, observation,
            )
            if result.status == "success":
                succeeded_actions.add(action_key)
            logger.info(
                f"[{task_id}] step {step}: OBSERVE [{result.status}] {observation}"
            )

        # Fell out of the loop without a "done" -> hit the cap.
        return self._summary(
            task_id, goal, "incomplete", False, actions_taken,
            self.max_steps, start, trace,
            reason=f"Reached max_steps={self.max_steps} without completion",
        )

    # ------------------------------------------------------------------
    # Think step
    # ------------------------------------------------------------------

    def _think(self, goal, history, correction=False):
        """Build the Think prompt and return the raw LLM response text."""
        prompt = self._think_prompt(goal, history, correction=correction)
        return self.llm.generate(prompt, max_tokens=300)

    def _think_prompt(self, goal, history, correction=False):
        tool_schemas = ToolRegistry.get_json_schemas()
        history_text = self._format_history(history)
        correction_block = f"\n{CORRECTION_NOTE}\n" if correction else ""

        return f"""You are a desktop automation agent that works in a Think-Act-Observe loop.

GOAL: {goal}

Available tools (JSON schemas):
{json.dumps(tool_schemas, indent=2)}

{history_text}

Decide the SINGLE next action that makes progress toward the GOAL.
Respond with ONLY one JSON object in this exact shape:
{{"thought": "<your reasoning>", "tool": "<tool_name>", "args": {{"key": "value"}}}}

Rules:
- Exactly ONE tool per step.
- Base your decision on the observations above. If a previous action FAILED,
  do not repeat it identically - use the error message to choose a corrected
  action.
- Do NOT repeat an action that already SUCCEEDED. Never take extra, duplicate,
  or unnecessary actions.
- The MOMENT the observations show that EVERY part of the GOAL has been
  accomplished, you MUST stop by responding with the done sentinel - do not
  perform any further actions:
  {{"thought": "<why the goal is complete>", "tool": "{DONE_TOOL}", "args": {{}}}}
{correction_block}
JSON:"""

    @staticmethod
    def _format_history(history):
        if not history:
            return "History so far: (none yet - this is the first step)"
        lines = ["History so far:"]
        for h in history:
            lines.append(f"Step {h['step']}:")
            lines.append(f"  Thought: {h['thought']}")
            lines.append(f"  Action: {h['tool']}({json.dumps(h['args'])})")
            lines.append(f"  Observation: [{h['status']}] {h['observation']}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_action(raw):
        """
        Extract a {thought, tool, args} object from the raw LLM text.

        Returns the parsed dict, or None if no valid JSON object with a "tool"
        field could be recovered (which triggers the retry logic).
        """
        if not raw:
            return None

        text = raw.strip()
        # Strip common code-fence wrappers the model sometimes adds.
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

        candidates = []
        # First try the whole string.
        candidates.append(text)
        # Then the first balanced {...} block, if any.
        block = ReActOrchestrator._first_json_object(text)
        if block:
            candidates.append(block)

        for candidate in candidates:
            try:
                obj = json.loads(candidate)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(obj, dict) and "tool" in obj:
                return obj
        return None

    @staticmethod
    def _action_key(tool, args):
        """Stable key for a (tool, args) pair, for redundant-action detection."""
        try:
            return (tool, json.dumps(args, sort_keys=True))
        except TypeError:
            return (tool, str(args))

    @staticmethod
    def _first_json_object(text):
        """Return the first brace-balanced {...} substring, or None."""
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        return None

    # ------------------------------------------------------------------
    # Summary helper
    # ------------------------------------------------------------------

    @staticmethod
    def _summary(task_id, goal, status, completed, actions_taken,
                 iterations, start, trace, reason):
        return {
            "task_id": task_id,
            "goal": goal,
            "status": status,
            "completed": completed,
            "actions_taken": actions_taken,
            "iterations": iterations,
            "elapsed_sec": round(time.perf_counter() - start, 2),
            "reason": reason,
            "trace": trace,
        }
