"""
Test script for the new structured tool system.
Run this to verify tools work before integrating into executor.

Usage:
    python test_tools.py
"""

import logging
import sys
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from agent.tools import ToolRegistry, get_tool_summary, initialize_tools
from models.vision import VisionAnalyzer

print("=" * 70)
print("TOOL SYSTEM TEST")
print("=" * 70)

# Initialize vision analyzer for screenshot tool
print("\n1. Initializing VisionAnalyzer...")
try:
    vision = VisionAnalyzer()
    initialize_tools(vision_analyzer=vision)
    print("   ✓ VisionAnalyzer initialized")
except Exception as e:
    print(f"   ✗ Failed to initialize VisionAnalyzer: {e}")
    vision = None

# Show registered tools
print("\n2. Registered Tools:")
summary = get_tool_summary()
print(f"   Total: {summary['total_tools']} tools")
for category, count in summary["by_category"].items():
    print(f"   - {category}: {count} tools")

print("\n3. Tool Details:")
for tool_info in summary["tools"]:
    print(f"   • {tool_info['name']} ({tool_info['category']})")
    print(f"     {tool_info['description']}")

# Test each tool
print("\n" + "=" * 70)
print("TOOL EXECUTION TESTS")
print("=" * 70)


def flush_stdin():
    """Flush stdin to prevent buffered input from previous tests"""
    try:
        import msvcrt

        while msvcrt.kbhit():
            msvcrt.getch()
    except ImportError:
        # Unix-like systems
        import termios

        termios.tcflush(sys.stdin, termios.TCIOFLUSH)


def safe_input(prompt):
    """Input with stdin flushing to prevent test interference"""
    # Wait a moment for any pending keyboard simulation to complete
    time.sleep(0.5)
    # Flush any buffered input
    try:
        flush_stdin()
    except Exception:
        pass
    return input(prompt)


def test_tool(tool_name, args_dict):
    """Test a single tool"""
    print(f"\n▶ Testing: {tool_name}")
    print(f"  Args: {args_dict}")

    tool = ToolRegistry.get_tool(tool_name)
    if not tool:
        print(f"  ✗ Tool '{tool_name}' not found!")
        return False

    try:
        # Validate arguments
        validated_args = tool.arguments_schema(**args_dict)
        print(f"  ✓ Arguments validated")

        # Execute
        result = tool.execute(validated_args)
        print(f"  Status: {result.status}")
        print(f"  Result: {result.result}")
        if result.data:
            print(f"  Data: {result.data}")

        return result.status == "success"

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


# Test 1: Wait (simplest, no side effects)
print("\n--- Test 1: wait ---")
test_tool("wait", {"seconds": 0.5})

# Test 2: Type text (will type in active window - be careful!)
print("\n--- Test 2: type_text ---")
print("⚠️  This will type text in your active window!")
response = safe_input("Continue? (y/n): ")
if response.lower() == "y":
    print(
        "  Starting in 2 seconds... switch to a safe window (like Notepad) if needed!"
    )
    time.sleep(2)
    test_tool("type_text", {"text": "Hello from agent!", "interval": 0.05})
    print("  ⚠️  Waiting 1 second to let typed text settle before next test...")
    time.sleep(1)
else:
    print("  Skipped")

# Test 3a: Click at current position
print("\n--- Test 3a: click (current position) ---")
print("⚠️  This will click the mouse at its current position!")
response = safe_input("Continue? (y/n): ")
if response.lower() == "y":
    test_tool("click", {})
else:
    print("  Skipped")

# Test 3b: Click at center
print("\n--- Test 3b: click (center position) ---")
print("⚠️  This will click the mouse at screen center!")
response = safe_input("Continue? (y/n): ")
if response.lower() == "y":
    test_tool("click", {"position": "center"})
else:
    print("  Skipped")

# Test 3c: Click at explicit coordinates
print("\n--- Test 3c: click (explicit x,y) ---")
print("⚠️  This will click at coordinates (100, 100)!")
response = safe_input("Continue? (y/n): ")
if response.lower() == "y":
    test_tool("click", {"x": 100, "y": 100})
else:
    print("  Skipped")

# Test 4: Open app
print("\n--- Test 4: open_app ---")
print("⚠️  This will open Notepad!")
response = safe_input("Continue? (y/n): ")
if response.lower() == "y":
    test_tool("open_app", {"app_name": "notepad"})
else:
    print("  Skipped")

# Test 5: Screenshot
print("\n--- Test 5: take_screenshot ---")
if vision:
    test_tool("take_screenshot", {"filepath": "test_screenshot.png"})
else:
    print("  Skipped (VisionAnalyzer not available)")

# Test error handling
print("\n" + "=" * 70)
print("ERROR HANDLING TESTS")
print("=" * 70)

# Test 1: Invalid tool
print("\n--- Test: Invalid tool name ---")
tool = ToolRegistry.get_tool("nonexistent_tool")
if tool is None:
    print("  ✓ Correctly returned None for invalid tool")
else:
    print("  ✗ Should have returned None")

# Test 2: Invalid arguments
print("\n--- Test: Invalid arguments (missing required field) ---")
tool = ToolRegistry.get_tool("wait")
try:
    # Missing 'seconds' field
    validated_args = tool.arguments_schema()
    print("  ✗ Should have raised validation error")
except Exception as e:
    print(f"  ✓ Correctly raised validation error: {e}")

# Test 3: Out of range argument
print("\n--- Test: Out of range argument ---")
try:
    # Seconds > 60 (max limit)
    validated_args = tool.arguments_schema(seconds=100)
    print("  ✗ Should have raised validation error")
except Exception as e:
    print(f"  ✓ Correctly raised validation error: {e}")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
print("\nIf all tests passed, the tool system is ready for integration!")
