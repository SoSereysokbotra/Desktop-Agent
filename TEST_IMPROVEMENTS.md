# Test Script Improvements

## Issue: Stdin Buffering in test_tools.py

### Problem
When `pyautogui.typewrite()` was executed in Test 2, it simulated keyboard input that went into the terminal's stdin buffer. This caused "Hello from agent!" to be read by the next `input()` call in Test 3, automatically answering the prompt and skipping the test.

### Root Cause
- `pyautogui.typewrite()` simulates keyboard events at the OS level
- These events are captured by the active window (the terminal running the test)
- The typed text remains buffered in stdin
- The next `input()` call reads this buffered text instead of waiting for user input

### Solution Implemented

#### 1. Added `flush_stdin()` function
```python
def flush_stdin():
    """Flush stdin to prevent buffered input from previous tests"""
    try:
        import msvcrt  # Windows
        while msvcrt.kbhit():
            msvcrt.getch()
    except ImportError:
        import termios  # Unix-like
        termios.tcflush(sys.stdin, termios.TCIOFLUSH)
```

#### 2. Added `safe_input()` wrapper
```python
def safe_input(prompt):
    """Input with stdin flushing to prevent test interference"""
    time.sleep(0.5)  # Wait for keyboard simulation to complete
    try:
        flush_stdin()  # Clear any buffered input
    except Exception:
        pass
    return input(prompt)
```

#### 3. Replaced all `input()` calls with `safe_input()`
All interactive prompts now use `safe_input()` instead of `input()`.

#### 4. Added delays and warnings
- Added 2-second countdown before `type_text` executes (user can switch windows)
- Added 1-second wait after `type_text` completes (let text settle)
- Warning messages now more explicit about what each test does

#### 5. Split click test into three separate tests
Instead of one "click" test, now have:
- **Test 3a**: Click at current position (no args)
- **Test 3b**: Click at center (`position="center"`)
- **Test 3c**: Click at explicit coordinates (`x=100, y=100`)

This ensures all three code paths in the `click` tool are tested.

## Test Flow After Fix

```
Test 1: wait               → No prompts, auto-runs
Test 2: type_text          → Prompt with safe_input() + 2s countdown + 1s cooldown
Test 3a: click (current)   → Prompt with safe_input()
Test 3b: click (center)    → Prompt with safe_input()
Test 3c: click (x,y)       → Prompt with safe_input()
Test 4: open_app          → Prompt with safe_input()
Test 5: take_screenshot   → Auto-runs if vision available
```

## Verification

Run `python test_tools.py` and answer "y" to all prompts. Each test should:
1. Wait for explicit "y" or "n" input (not auto-skip)
2. Execute the tool correctly
3. Display results
4. Not interfere with subsequent tests

## Notes

- `flush_stdin()` is platform-specific (Windows uses `msvcrt`, Unix uses `termios`)
- The 0.5s delay in `safe_input()` ensures keyboard simulation completes before flushing
- This pattern should be used for any interactive test that runs tools with keyboard simulation
