# Tool Audit - Error Handling Fixes

## Issue Found
**Bug**: `take_screenshot` was returning `status="success"` with `result="Screenshot saved to None"` when the underlying screenshot call failed, because `VisionAnalyzer.save_screenshot()` returns `None` on failure instead of raising an exception.

## Audit Results

### ✅ Fixed: `take_screenshot` (screen_tools.py)
**Problem**: `save_screenshot()` returns `None` on failure (line 76 in vision.py)
**Fix**: Added explicit `None` check after calling `save_screenshot()`:
```python
saved_path = self.vision.save_screenshot(filepath)

# Check if save_screenshot returned None (failure)
if saved_path is None:
    return ToolResult.error(
        result="Screenshot failed - could not capture or save image",
        data={"error": "save_screenshot returned None", "filepath": args.filepath}
    )
```

### ✅ Improved: `open_app` (app_tools.py)
**Potential Issue**: Could catch all exceptions generically
**Fix**: Added explicit handling for `OSError` (separate from `FileNotFoundError`):
- `FileNotFoundError`: Application not found
- `OSError`: System-level failures (permissions, invalid path format, etc.)
- Generic `Exception`: Catch-all for unexpected issues

All now properly return `status="error"` with descriptive messages.

### ✅ Improved: `type_text` (input_tools.py)
**Already Correct**: Has try/except that catches all pyautogui exceptions
**Improvement**: Added comment clarifying that `pyautogui.typewrite()` raises exceptions for unsupported characters (non-ASCII)
**Additional Fix**: Now includes `text` in error data for debugging

### ✅ Improved: `click` (input_tools.py)
**Potential Issue**: `pyautogui.size()` and `pyautogui.position()` could fail in headless/no-display environments
**Fix**: Added nested try/except blocks for:
- Getting screen size (for "center" position)
- Getting current mouse position
- Invalid position names now include the invalid value in error data

All failures properly return `status="error"`.

### ✅ Verified: `wait` (system_tools.py)
**Status**: Already correct
- `time.sleep()` is wrapped in try/except
- Pydantic validation prevents negative or excessively large values (0-60 second range)
- Returns actual wait time in data field

## Summary of Changes

| Tool | Status | Change Type |
|------|--------|-------------|
| `take_screenshot` | **FIXED** | Added `None` check |
| `open_app` | **IMPROVED** | Separate OSError handling |
| `type_text` | **IMPROVED** | Better error data |
| `click` | **IMPROVED** | Nested error handling |
| `wait` | **VERIFIED** | No changes needed |

## Testing Recommendations

1. **Screenshot failure**: Temporarily break PIL/pyscreeze import to verify error status
2. **Invalid app**: Test `open_app({"app_name": "nonexistent123"})` → should return error
3. **Unsupported characters**: Test `type_text({"text": "Hello 你好"})` → should return error (non-ASCII)
4. **Invalid click position**: Test `click({"position": "invalid"})` → should return error
5. **Out of range wait**: Already prevented by Pydantic validation (ge=0, le=60)

## Key Principle Established

**All tools must return `status="error"` for actual failures, not `status="success"` with caveat messages.**

When a tool's underlying operation:
- Returns `None` or falsy value → Check and return error
- Raises an exception → Catch and return error
- Succeeds partially → Still return error (fail fast, no partial successes)

No tool should return success unless the operation genuinely completed as intended.
