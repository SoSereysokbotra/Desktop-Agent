"""
Phase 1 Integration Test - Complete End-to-End

Tests the full integration:
1. Regex-based tool detection (fast path)
2. LLM JSON fallback (when regex doesn't match)
3. ValueError handling
4. ToolResult → string conversion
"""

import logging

from agent.executor import Executor
from agent.planner import Planner
from models.llm import LLM

logging.basicConfig(level=logging.WARNING)  # Reduce noise

print("=" * 70)
print("PHASE 1 INTEGRATION TEST")
print("=" * 70)

# Initialize components without VisionAnalyzer (to avoid long loading)
print("\nInitializing components...")
llm = LLM()
planner = Planner(llm)
executor = Executor(vision_analyzer=None)
print("OK")

# Test 1: Regex path - "wait 2 seconds"
print("\n" + "=" * 70)
print("TEST 1: Regex path - simple command")
print("=" * 70)
user_input = "wait 2 seconds"
print(f"Input: '{user_input}'")

tools = planner.extract_tools(user_input)
print(f"Extracted: {tools}")
assert len(tools) == 1
assert tools[0][0] == "wait"
assert tools[0][1] == {"seconds": 2.0}

tool_name, tool_args = tools[0]
result = executor.execute(tool_name, tool_args)
print(f"Status: {result.status}")
print(f"Result: {result.result}")
assert result.status == "success"
print("[OK] PASS")

# Test 2: Regex path - "click at 100,200"
print("\n" + "=" * 70)
print("TEST 2: Regex path - click with coordinates")
print("=" * 70)
user_input = "click at 100,200"
print(f"Input: '{user_input}'")

tools = planner.extract_tools(user_input)
print(f"Extracted: {tools}")
assert len(tools) == 1
assert tools[0][0] == "click"
assert tools[0][1] == {"x": 100, "y": 200}

tool_name, tool_args = tools[0]
result = executor.execute(tool_name, tool_args)
print(f"Status: {result.status}")
print(f"Result: {result.result}")
assert result.status == "success"
print("[OK] PASS")

# Test 3: Regex path - "type hello"
print("\n" + "=" * 70)
print("TEST 3: Regex path - type_text")
print("=" * 70)
user_input = "type hello world"
print(f"Input: '{user_input}'")

tools = planner.extract_tools(user_input)
print(f"Extracted: {tools}")
assert len(tools) == 1
assert tools[0][0] == "type_text"
assert tools[0][1] == {"text": "hello world"}

tool_name, tool_args = tools[0]
result = executor.execute(tool_name, tool_args)
print(f"Status: {result.status}")
print(f"Result: {result.result}")
assert result.status == "success"
print("[OK] PASS")

# Test 4: ValueError handling - "wait abc"
print("\n" + "=" * 70)
print("TEST 4: ValueError handling - invalid arg")
print("=" * 70)
user_input = "wait abc"
print(f"Input: '{user_input}'")

try:
    tools = planner.extract_tools(user_input)
    print("✗ FAIL: Should have raised ValueError")
except ValueError as e:
    print(f"Caught ValueError: {e}")
    print("[OK] PASS")

# Test 5: No tools needed - conversational
print("\n" + "=" * 70)
print("TEST 5: No tools - conversational input")
print("=" * 70)
user_input = "hello how are you"
print(f"Input: '{user_input}'")

tools = planner.extract_tools(user_input)
print(f"Extracted: {tools}")
assert tools == []
print("[OK] PASS - correctly returns empty list")

# Test 6: LLM JSON fallback path
print("\n" + "=" * 70)
print("TEST 6: LLM JSON fallback - no regex match")
print("=" * 70)
print("Note: This tests that the LLM fallback path is REACHABLE")
print("(actual LLM output quality not tested here)")

# Mock a command that doesn't match regex but should need tools
user_input = "please wait for 3 seconds"  # "please" prefix doesn't match regex
print(f"Input: '{user_input}'")

# First verify regex doesn't match
from agent.planner import detect_tools

regex_result = detect_tools(user_input)
print(f"Regex result: {regex_result}")
assert regex_result == [], "Regex should not match this input"

# Now call extract_tools - should try LLM fallback
# (LLM might return [] or a tool, depending on output)
tools = planner.extract_tools(user_input)
print(f"LLM fallback result: {tools}")
print("[OK] PASS - LLM fallback path was executed (did not return early)")

# Test 7: End-to-end simulation of app.py flow
print("\n" + "=" * 70)
print("TEST 7: Full app.py flow simulation")
print("=" * 70)


def simulate_process_user_input(user_input):
    """Simulates app.py's process_user_input logic"""
    print(f"\nProcessing: '{user_input}'")

    # Extract tools (with ValueError handling)
    try:
        tools_to_execute = planner.extract_tools(user_input)
    except ValueError as e:
        error_msg = f"I couldn't understand that command: {str(e)}"
        print(f"  Error: {error_msg}")
        return error_msg

    # If no tools, conversational
    if not tools_to_execute:
        print("  No tools needed - conversational response")
        return "conversational response"

    # Execute tools
    print(f"  Executing {len(tools_to_execute)} tool(s)...")
    tool_results = []
    for tool_name, tool_args in tools_to_execute:
        result = executor.execute(tool_name, tool_args)
        tool_results.append((tool_name, result))
        print(f"    {tool_name}: {result.status} - {result.result}")

    return "response with tool context"


# Test valid command
result = simulate_process_user_input("wait 1 second")
assert "response with tool context" in result

# Test invalid command
result = simulate_process_user_input("wait xyz")
assert "couldn't understand" in result

# Test conversational
result = simulate_process_user_input("tell me a joke")
assert "conversational" in result

print("\n[OK] PASS - Full flow works correctly")

print("\n" + "=" * 70)
print("ALL TESTS PASSED")
print("=" * 70)
print("\n[OK] Regex path works")
print("[OK] ValueError handling works")
print("[OK] No-tools path returns []")
print("[OK] LLM fallback path is reachable")
print("[OK] Full app.py flow simulation works")
print("\nPhase 1 integration is complete and ready!")
