"""
Executor - Execute tools and desktop automation commands
This is where the actual work happens
"""

import logging
import pyautogui
import time
import subprocess
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class Executor:
    def __init__(self, vision_analyzer=None):
        self.vision = vision_analyzer
        self.last_screenshot = None
        
        # Tool registry - map tool names to functions
        self.tools = {
            # App control
            "open_app": self.open_app,
            "open_chrome": self.open_chrome,
            "open_notepad": self.open_notepad,
            "open_vscode": self.open_vscode,
            "open_calculator": self.open_calculator,
            "close_app": self.close_app,
            
            # Keyboard/Mouse
            "type": self.type_text,
            "click": self.click,
            "press_key": self.press_key,
            "move_mouse": self.move_mouse,
            "scroll": self.scroll,
            
            # Screen
            "screenshot": self.take_screenshot,
            "analyze_screen": self.analyze_screen,
            
            # System
            "wait": self.wait,
            "list_open_windows": self.list_open_windows,
            "get_screen_size": self.get_screen_size,
        }
    
    def execute(self, tool_name, args=None):
        """
        Execute a tool
        
        Args:
            tool_name: Name of the tool to execute
            args: Arguments (can be string or dict)
            
        Returns:
            String describing the result
        """
        tool_name = tool_name.lower().strip()
        
        # Try direct match
        if tool_name in self.tools:
            tool_func = self.tools[tool_name]
        else:
            # Strategy 1: Replace underscores/spaces with each other
            alt_names = [
                tool_name.replace("_", " "),
                tool_name.replace(" ", "_"),
                tool_name.replace("browser", "").strip(),
                tool_name.replace("app", "").strip(),
                tool_name.replace("application", "").strip(),
            ]
            
            # Additional strategies (e.g., adding/removing "open_")
            if not tool_name.startswith("open_"):
                alt_names.append("open_" + tool_name)
                alt_names.append("open_" + tool_name.replace(" ", "_"))
            
            matched = False
            for alt_name in alt_names:
                if alt_name in self.tools:
                    tool_func = self.tools[alt_name]
                    matched = True
                    break
            
            if not matched:
                logger.warning(f"Unknown tool: {tool_name}")
                return f"Unknown tool: {tool_name}"
        
        try:
            result = tool_func(args)
            logger.info(f"Tool {tool_name} executed: {result}")
            return result
        
        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}", exc_info=True)
            return f"Error executing {tool_name}: {str(e)}"
    
    # ============ App Control ============
    
    def open_app(self, app_name):
        """Open an application by name"""
        if not app_name:
            return "No app name provided"
        
        app_name = app_name.lower().strip()
        
        try:
            # Windows app launching
            os.startfile(app_name)
            time.sleep(2)  # Wait for app to open
            return f"Opened {app_name}"
        except Exception as e:
            logger.error(f"Could not open {app_name}: {e}")
            return f"Could not open {app_name}"
    
    def open_chrome(self, args=None):
        """Open Google Chrome"""
        try:
            # Try common Chrome paths on Windows
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ]
            
            for path in chrome_paths:
                if os.path.exists(path):
                    subprocess.Popen(path)
                    time.sleep(3)
                    return "Chrome opened"
            
            # Fallback
            os.startfile("chrome")
            return "Chrome opened"
        except Exception as e:
            return f"Could not open Chrome: {e}"
    
    def open_notepad(self, args=None):
        """Open Notepad"""
        try:
            os.startfile("notepad")
            time.sleep(1)
            return "Notepad opened"
        except Exception as e:
            return f"Could not open Notepad: {e}"
    
    def open_vscode(self, args=None):
        """Open VS Code"""
        try:
            subprocess.Popen("code")
            time.sleep(2)
            return "VS Code opened"
        except Exception as e:
            return f"Could not open VS Code: {e}"
    
    def open_calculator(self, args=None):
        """Open Calculator"""
        try:
            os.startfile("calc")
            time.sleep(1)
            return "Calculator opened"
        except Exception as e:
            return f"Could not open Calculator: {e}"
    
    def close_app(self, app_name):
        """Close an application"""
        if not app_name:
            return "No app name provided"
        
        try:
            os.system(f"taskkill /IM {app_name}.exe /F")
            return f"Closed {app_name}"
        except Exception as e:
            return f"Could not close {app_name}: {e}"
    
    # ============ Keyboard/Mouse ============
    
    def type_text(self, text):
        """Type text"""
        if not text:
            return "No text provided"
        
        try:
            # Small delay between characters for stability
            pyautogui.typewrite(text, interval=0.05)
            return f"Typed: {text}"
        except Exception as e:
            return f"Could not type: {e}"
    
    def click(self, position=None):
        """
        Click at position
        position: "center", (x, y), or None for current cursor
        """
        try:
            if position == "center":
                # Click center of screen
                x, y = pyautogui.size()
                pyautogui.click(x // 2, y // 2)
                return "Clicked center"
            elif isinstance(position, str) and "," in position:
                # Parse "x,y"
                x, y = map(int, position.split(","))
                pyautogui.click(x, y)
                return f"Clicked at {x}, {y}"
            else:
                pyautogui.click()
                return "Clicked"
        except Exception as e:
            return f"Click error: {e}"
    
    def press_key(self, key):
        """Press a key"""
        if not key:
            return "No key provided"
        
        try:
            pyautogui.press(key)
            return f"Pressed {key}"
        except Exception as e:
            return f"Could not press {key}: {e}"
    
    def move_mouse(self, position):
        """
        Move mouse to position
        position: "center" or "x,y"
        """
        try:
            if position == "center":
                x, y = pyautogui.size()
                pyautogui.moveTo(x // 2, y // 2)
                return "Moved to center"
            elif "," in position:
                x, y = map(int, position.split(","))
                pyautogui.moveTo(x, y)
                return f"Moved to {x}, {y}"
            else:
                return "Invalid position format"
        except Exception as e:
            return f"Mouse error: {e}"
    
    def scroll(self, direction_and_amount):
        """
        Scroll
        direction_and_amount: "up:5" or "down:10"
        """
        try:
            if ":" in direction_and_amount:
                direction, amount = direction_and_amount.split(":")
                amount = int(amount)
                
                if direction.lower() == "up":
                    pyautogui.scroll(amount)
                elif direction.lower() == "down":
                    pyautogui.scroll(-amount)
                
                return f"Scrolled {direction} {amount}"
            else:
                return "Invalid scroll format"
        except Exception as e:
            return f"Scroll error: {e}"
    
    # ============ Screen ============
    
    def take_screenshot(self, args=None):
        """Take a screenshot"""
        try:
            filepath = "screenshot.png"
            if self.vision:
                filepath = self.vision.save_screenshot(filepath)
            self.last_screenshot = filepath
            return f"Screenshot saved to {filepath}"
        except Exception as e:
            return f"Screenshot error: {e}"
    
    def analyze_screen(self, args=None):
        """Analyze what's on the screen"""
        try:
            if self.vision:
                description = self.vision.analyze_current_screen()
                return description
            else:
                return "Vision module not available"
        except Exception as e:
            return f"Screen analysis error: {e}"
    
    # ============ System ============
    
    def wait(self, seconds):
        """Wait/sleep"""
        try:
            duration = float(seconds) if seconds else 1
            time.sleep(duration)
            return f"Waited {duration} seconds"
        except Exception as e:
            return f"Wait error: {e}"
    
    def list_open_windows(self, args=None):
        """List open windows (Windows-specific)"""
        try:
            result = subprocess.check_output(
                "tasklist",
                universal_newlines=True
            )
            # Show first 500 chars
            return result[:500]
        except Exception as e:
            return f"Could not list windows: {e}"
    
    def get_screen_size(self, args=None):
        """Get screen resolution"""
        try:
            width, height = pyautogui.size()
            return f"Screen size: {width}x{height}"
        except Exception as e:
            return f"Could not get screen size: {e}"