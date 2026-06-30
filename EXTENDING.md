# Implementation Guide - Extending the Agent

This guide shows you how to add new capabilities to your agent.

## Adding New Tools

### Step 1: Add the Tool Function

Edit `agent/executor.py`:

```python
# In the Executor class, add your function

def open_spotify(self, args=None):
    """Open Spotify"""
    try:
        os.startfile("spotify")
        time.sleep(2)
        return "Spotify opened"
    except Exception as e:
        return f"Could not open Spotify: {e}"
```

### Step 2: Register the Tool

In the same file, find the `__init__` method where tools are registered:

```python
self.tools = {
    # ... existing tools ...
    "open_spotify": self.open_spotify,  # Add this line
}
```

### Step 3: Test It

```bash
python app.py
```

Then type: `Open Spotify`

That's it! The LLM will automatically discover and use new tools.

---

## Example: File Operations Tool

Here's a complete example of a file tool:

```python
# In agent/executor.py, add to Executor class:

def read_file(self, filepath):
    """Read a text file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        # Return first 500 chars if large
        if len(content) > 500:
            return content[:500] + "... (truncated)"
        return content
    except FileNotFoundError:
        return f"File not found: {filepath}"
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(self, filepath_and_content):
    """Write to a file
    Args: "filepath|content" (pipe-separated)
    """
    try:
        filepath, content = filepath_and_content.split("|", 1)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Wrote to {filepath}"
    except Exception as e:
        return f"Error writing file: {e}"

def delete_file(self, filepath):
    """Delete a file"""
    try:
        import os
        os.remove(filepath)
        return f"Deleted {filepath}"
    except Exception as e:
        return f"Error deleting file: {e}"
```

Then register them:
```python
self.tools = {
    # ... existing ...
    "read_file": self.read_file,
    "write_file": self.write_file,
    "delete_file": self.delete_file,
}
```

Now you can use:
```
Read my notes from documents\notes.txt
Write "Hello World" to test.txt
Delete old_file.txt
```

---

## Example: Web Search Tool

Add web capabilities:

```python
def google_search(self, query):
    """Search Google (returns description of top result)"""
    try:
        import webbrowser
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        webbrowser.open(url)
        return f"Searched Google for: {query}"
    except Exception as e:
        return f"Search error: {e}"

def open_url(self, url):
    """Open a URL in browser"""
    try:
        import webbrowser
        webbrowser.open(url)
        return f"Opened {url}"
    except Exception as e:
        return f"Error opening URL: {e}"
```

Register:
```python
"google_search": self.google_search,
"open_url": self.open_url,
```

Usage:
```
Search for Python tutorials
Open github.com
```

---

## Example: Clipboard Operations

```python
def copy_to_clipboard(self, text):
    """Copy text to clipboard"""
    try:
        import pyperclip
        pyperclip.copy(text)
        return f"Copied to clipboard: {text[:50]}..."
    except Exception as e:
        return f"Clipboard error: {e}"

def paste_from_clipboard(self, args=None):
    """Paste from clipboard"""
    try:
        import pyperclip
        content = pyperclip.paste()
        # Type it
        pyautogui.typewrite(content, interval=0.02)
        return "Pasted from clipboard"
    except Exception as e:
        return f"Clipboard error: {e}"
```

---

## Example: Email Tool

```python
def send_email(self, to_and_subject):
    """Send email
    Args: "email@example.com|Subject here"
    """
    try:
        to, subject = to_and_subject.split("|", 1)
        
        import smtplib
        from email.mime.text import MIMEText
        
        # Configure with your email
        sender_email = "your_email@gmail.com"
        sender_password = "your_app_password"  # Use app-specific password
        
        msg = MIMEText("Message body")
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = to
        
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        
        return f"Email sent to {to}"
    except Exception as e:
        return f"Email error: {e}"
```

**Security note:** Store credentials in environment variables:
```python
import os
sender_password = os.getenv('GMAIL_PASSWORD')
```

---

## Improving Tool Decisions

Right now the LLM is simple about tool selection. You can improve it:

### Option 1: Tool Descriptions

Add a tool info registry:

```python
# In agent/executor.py

TOOL_DESCRIPTIONS = {
    "open_app": "Open an application by name (Chrome, Notepad, etc)",
    "read_file": "Read contents of a text file",
    "type": "Type text on the keyboard",
    "screenshot": "Take a screenshot of the screen",
    "google_search": "Search Google for information",
}
```

Then update the LLM prompt to include descriptions.

### Option 2: Tool Chaining

Some requests need multiple tools in sequence:

```python
# In agent/planner.py

def should_chain_tools(self, user_input):
    """Detect if multiple tools are needed"""
    chains = {
        "search": ["google_search", "analyze_screen"],
        "document": ["read_file", "type"],
        "screenshot": ["screenshot", "analyze_screen"],
    }
    
    for chain_keyword, tools in chains.items():
        if chain_keyword in user_input.lower():
            return tools
    
    return None
```

Then execute them in sequence.

---

## Advanced: Custom Tool Arguments

Tools can accept structured arguments:

```python
def advanced_click(self, args):
    """Click with more options
    Args could be:
      - {"x": 500, "y": 300}
      - {"region": "center"}
      - {"button": "right"}
    """
    try:
        if isinstance(args, str):
            # Parse from "x:500,y:300" format
            import json
            args = json.loads(args.replace("'", '"'))
        
        x = args.get('x', pyautogui.position()[0])
        y = args.get('y', pyautogui.position()[1])
        button = args.get('button', 'left')
        
        pyautogui.click(x, y, button=button)
        return f"Clicked at {x},{y} with {button} button"
    except Exception as e:
        return f"Click error: {e}"
```

---

## Version Roadmap

**V3 (Current):** Basic chat + tools + desktop automation + vision
- ✅ Chat with LLM
- ✅ Tool discovery and execution
- ✅ Desktop control
- ✅ Screenshot analysis

**V4:** Rich Tools Library
- File operations (read, write, delete, search)
- Browser control
- System info
- Clipboard management
- Application shortcuts

**V5:** Smart Planning
- Multi-step command chains
- Result verification
- Error recovery
- Context awareness from previous steps

**V6:** Voice Interface
- Speech-to-text input
- Text-to-speech output
- Microphone listening
- Wake word detection

**V7:** Production Ready
- Error logging and monitoring
- Tool usage statistics
- User preference learning
- Performance optimization
- Security hardening

**V8:** ESP32 Integration
- REST API wrapper
- WiFi communication
- Voice command forwarding
- Real-time control

---

## Testing New Tools

Always test manually first:

```python
# Quick test script - test_tools.py

from agent.executor import Executor
from models.vision import VisionAnalyzer

executor = Executor(VisionAnalyzer())

# Test your new tool
result = executor.execute("your_tool_name", "test_argument")
print(result)
```

Run:
```bash
python test_tools.py
```

---

## Performance Tips

1. **Batch Operations**
   ```python
   # Instead of multiple clicks, type them together
   pyautogui.typewrite("command1; command2", interval=0.05)
   ```

2. **Cache Vision Results**
   ```python
   # Don't reanalyze the same screenshot
   if self.last_screenshot == current:
       return self.last_analysis
   ```

3. **Use Fast Models**
   - Vision: `microsoft/git-base` (faster than BLIP)
   - LLM: Qwen 0.5B is small but adequate

---

## Debugging Tools

Add this to any tool:

```python
def tool_with_logging(self, args):
    logger.debug(f"Tool called with args: {args}")
    logger.debug(f"Current state: {pyautogui.position()}")
    
    try:
        result = ...
        logger.info(f"Tool succeeded: {result}")
        return result
    except Exception as e:
        logger.error(f"Tool failed: {e}", exc_info=True)
        raise
```

Then enable DEBUG logging to see detailed execution.

---

## Next Challenge

After you implement V3 & V4, the real challenge is **V5: Planning**.

Getting an LLM to successfully execute multi-step commands requires:
1. Breaking down user intent into sub-tasks
2. Executing them in order
3. Checking if each step succeeded
4. Adapting if something fails

That's where it becomes truly interesting.

**Your first hard problem to solve:** Make the agent handle:
```
"Open Chrome, go to GitHub, and show me my repositories"
```

This requires chaining 3+ tools and understanding the results of each.

---

Good luck! Add tools one at a time and test. The architecture is solid—just keep building on it.