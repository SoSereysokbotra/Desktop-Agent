"""
Test executor.py integration with tool registry

Verifies that the refactored executor works correctly before
integrating with planner.py
"""

import logging

from agent.executor import Executor
from models.vision import VisionAnalyzer

logging.basicConfig(level=logging.INFO)

print("=" * 70)
print("EXECUTOR INTEGRATION TEST")
print("=" * 70)

# Initialize executor with vision
print("\n1. Initializing Executor with VisionAnalyzer...")
try:
    vision = VisionAnalyzer()
    executor = Executor(vision_analyzer=vision)
    print(
        f"   [OK] Executor initialized with {len(executor.get_available_tools())} tools"
    )
    print(f"   Available tools: {', '.join(executor.get_available_tools())}")
except Exception as e:
    print(f"   [FAIL] Failed: {e}")
    exit(1)

print("\n" + "=" * 70)
print("TEST 1: Dict-based args (new format)")
print("=" * 70)

# Test 1a: wait with dict args
print("\n1a. wait with dict args: {'seconds': 0.5}")
result = executor.execute("wait", {"seconds": 0.5})
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
print(f"   Data: {result.data}")
assert result.status == "success", "wait should succeed"

# Test 1b: type_text with dict args
print("\n1b. type_text with dict args: {'text': 'test', 'interval': 0.01}")
result = executor.execute("type_text", {"text": "test", "interval": 0.01})
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
assert result.status == "success", "type_text should succeed"

print("\n" + "=" * 70)
print("TEST 2: String args (backward compatibility)")
print("=" * 70)

# Test 2a: open_app with string arg
print("\n2a. open_app with string arg: 'notepad'")
result = executor.execute("open_app", "notepad")
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
print(f"   Data: {result.data}")
assert result.status in ("success", "error"), "Should return valid status"
if result.status == "error":
    print("   Note: Expected if notepad not found, that's OK")

# Test 2b: wait with string arg
print("\n2b. wait with string arg: '0.3'")
result = executor.execute("wait", "0.3")
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
assert result.status == "success", "wait with string should work"

print("\n" + "=" * 70)
print("TEST 3: No args (None)")
print("=" * 70)

# Test 3a: take_screenshot with None
print("\n3a. take_screenshot with None (should use default filepath)")
result = executor.execute("take_screenshot", None)
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
print(f"   Data: {result.data}")
assert result.status == "success", "screenshot should succeed"

# Test 3b: click with None
print("\n3b. click with None (should click current position)")
result = executor.execute("click", None)
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
assert result.status == "success", "click should succeed"

print("\n" + "=" * 70)
print("TEST 4: Error handling")
print("=" * 70)

# Test 4a: Invalid tool name
print("\n4a. Invalid tool name: 'nonexistent_tool'")
result = executor.execute("nonexistent_tool", None)
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
assert result.status == "error", "Should return error for invalid tool"
assert "available_tools" in result.data, "Should list available tools"

# Test 4b: Invalid args (out of range)
print("\n4b. Invalid args: wait with seconds=100 (exceeds max 60)")
result = executor.execute("wait", {"seconds": 100})
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
assert result.status == "error", "Should return error for invalid args"

# Test 4c: Empty required field
print("\n4c. Empty required field: type_text with empty text")
result = executor.execute("type_text", {"text": ""})
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
assert result.status == "error", "Should return error for empty text"

# Test 4d: Invalid string arg - wait with non-numeric
print("\n4d. Invalid string arg: wait with 'abc' (non-numeric)")
result = executor.execute("wait", "abc")
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
assert result.status == "error", "Should return error for non-numeric wait"
assert (
    "could not convert" in result.result.lower() or "invalid" in result.result.lower()
), "Should mention conversion error"

# Test 4e: Invalid string arg - click with malformed coords
print("\n4e. Invalid string arg: click with '100,abc' (bad coords)")
result = executor.execute("click", "100,abc")
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
assert result.status == "error", "Should return error for malformed coordinates"
assert (
    "invalid" in result.result.lower() or "could not convert" in result.result.lower()
), "Should mention conversion error"

print("\n" + "=" * 70)
print("TEST 5: Click position formats")
print("=" * 70)

# Test 5a: Click with "center" string (old format)
print("\n5a. click with string 'center' (backward compat)")
result = executor.execute("click", "center")
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
assert result.status == "success", "click center should work"

# Test 5b: Click with explicit coords dict (new format)
print("\n5b. click with dict {'x': 100, 'y': 100}")
result = executor.execute("click", {"x": 100, "y": 100})
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
assert result.status == "success", "click with coords should work"

print("\n" + "=" * 70)
print("ALL TESTS PASSED")
print("=" * 70)
print("\n✓ Executor.execute() returns ToolResult objects")
print("✓ Dict args work (new format)")
print("✓ String args work (backward compatibility)")
print("✓ None args work (defaults)")
print("✓ Error handling returns proper status='error'")
print("✓ Click position parsing works for all formats")
print("\nExecutor integration ready for planner.py!")
