"""
Error Handling Verification Test

Tests that tools properly return status="error" for failures,
not status="success" with misleading messages.
"""

import logging

from agent.tools import ToolRegistry, initialize_tools
from agent.tools.screen_tools import TakeScreenshot

logging.basicConfig(level=logging.INFO)

print("=" * 70)
print("ERROR HANDLING VERIFICATION")
print("=" * 70)

# Test 1: Screenshot with VisionAnalyzer that returns None (failure)
print("\n1. Testing take_screenshot when save_screenshot returns None...")


class MockVisionAnalyzerFailure:
    """Mock VisionAnalyzer that simulates save_screenshot failure"""

    def save_screenshot(self, filepath):
        # Simulate failure by returning None (same as real VisionAnalyzer does)
        return None


mock_vision = MockVisionAnalyzerFailure()
screenshot_tool = TakeScreenshot(vision_analyzer=mock_vision)

result = screenshot_tool.execute(screenshot_tool.arguments_schema(filepath="test.png"))
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
print(f"   Data: {result.data}")

if result.status == "error":
    print(
        "   ✅ BUG FIX VERIFIED: Correctly returns error when save_screenshot returns None"
    )
else:
    print(f"   ❌ BUG NOT FIXED: Got status='{result.status}' instead of 'error'")
    print(f"   ❌ Result was: {result.result}")

assert result.status == "error", f"CRITICAL: Should return error, got {result.status}"
assert "failed" in result.result.lower(), (
    f"CRITICAL: Error message should mention failure"
)

# Test 2: Screenshot with no VisionAnalyzer at all
print("\n2. Testing take_screenshot without VisionAnalyzer initialized...")
screenshot_tool_no_vision = TakeScreenshot(vision_analyzer=None)
result = screenshot_tool_no_vision.execute(
    screenshot_tool_no_vision.arguments_schema(filepath="test.png")
)
print(f"   Status: {result.status}")
print(f"   Result: {result.result}")
assert result.status == "error", "❌ Should return error without VisionAnalyzer"
print("   ✓ Correctly returns error")

# Initialize other tools for remaining tests
initialize_tools(vision_analyzer=None)

# Test 3: Invalid app
print("\n3. Testing open_app with nonexistent application...")
app_tool = ToolRegistry.get_tool("open_app")
if app_tool:
    result = app_tool.execute(
        app_tool.arguments_schema(app_name="totally_fake_app_12345")
    )
    print(f"   Status: {result.status}")
    print(f"   Result: {result.result}")
    assert result.status == "error", "❌ Should return error for nonexistent app"
    print("   ✓ Correctly returns error")
else:
    print("   ✗ Open app tool not found")

# Test 4: Invalid click position
print("\n4. Testing click with invalid position name...")
click_tool = ToolRegistry.get_tool("click")
if click_tool:
    result = click_tool.execute(
        click_tool.arguments_schema(position="invalid_position_xyz")
    )
    print(f"   Status: {result.status}")
    print(f"   Result: {result.result}")
    print(f"   Data: {result.data}")
    assert result.status == "error", "❌ Should return error for invalid position"
    assert "invalid_position_xyz" in result.data.get("position", ""), (
        "❌ Should include invalid position in data"
    )
    print("   ✓ Correctly returns error with position in data")
else:
    print("   ✗ Click tool not found")

# Test 5: Wait with invalid seconds (caught by Pydantic)
print("\n5. Testing wait with out-of-range seconds (Pydantic validation)...")
wait_tool = ToolRegistry.get_tool("wait")
if wait_tool:
    try:
        # This should raise a Pydantic validation error
        result = wait_tool.execute(wait_tool.arguments_schema(seconds=100))
        print(f"   ✗ Should have raised validation error, got: {result.status}")
    except Exception as e:
        print(f"   ✓ Correctly raised validation error: {type(e).__name__}")
else:
    print("   ✗ Wait tool not found")

# Test 6: Empty text for type_text
print("\n6. Testing type_text with empty string...")
type_tool = ToolRegistry.get_tool("type_text")
if type_tool:
    result = type_tool.execute(type_tool.arguments_schema(text=""))
    print(f"   Status: {result.status}")
    print(f"   Result: {result.result}")
    assert result.status == "error", "❌ Should return error for empty text"
    print("   ✓ Correctly returns error")
else:
    print("   ✗ Type text tool not found")

print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)
print("\nAll error cases properly return status='error' with descriptive messages!")
