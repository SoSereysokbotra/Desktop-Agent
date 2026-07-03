"""
Quick executor test without VisionAnalyzer (to avoid long loading times)
"""

import logging

from agent.executor import Executor

logging.basicConfig(level=logging.WARNING)  # Reduce noise

print("Testing executor.execute() error handling...")

# Initialize without vision
executor = Executor(vision_analyzer=None)

# Test 1: Invalid string -> float conversion
print("\n1. wait with 'abc' (invalid float)")
result = executor.execute("wait", "abc")
print(f"   Status: {result.status}")
print(f"   Result: {result.result[:80]}...")
assert result.status == "error", "Should be error"
assert (
    "could not convert" in result.result.lower() or "invalid" in result.result.lower()
)
print("   [PASS]")

# Test 2: Invalid string -> int,int conversion
print("\n2. click with '100,abc' (invalid coords)")
result = executor.execute("click", "100,abc")
print(f"   Status: {result.status}")
print(f"   Result: {result.result[:80]}...")
assert result.status == "error", "Should be error"
assert (
    "invalid" in result.result.lower() or "could not convert" in result.result.lower()
)
print("   [PASS]")

# Test 3: Valid wait
print("\n3. wait with '0.5' (valid)")
result = executor.execute("wait", "0.5")
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
assert result.status == "success"
print("   [PASS]")

# Test 4: Valid click position
print("\n4. click with 'center' (valid)")
result = executor.execute("click", "center")
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
assert result.status == "success"
print("   [PASS]")

# Test 5: Valid click coords
print("\n5. click with '100,200' (valid)")
result = executor.execute("click", "100,200")
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
assert result.status == "success"
print("   [PASS]")

print("\n" + "=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)
print("\nExecutor properly converts ValueError to ToolResult.error()")
print("Ready for planner.py integration!")
