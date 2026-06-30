"""
Vision capabilities - screenshot and image understanding
Uses a lightweight vision model from HuggingFace
"""

import logging
import pyautogui
from PIL import Image
import io
import torch
from transformers import pipeline

logger = logging.getLogger(__name__)


class VisionAnalyzer:
    def __init__(self, model_name="Salesforce/blip-image-captioning-base"):
        """
        Initialize vision model for image understanding
        
        Args:
            model_name: HuggingFace vision model ID
            
        Options:
          - "Salesforce/blip-image-captioning-base" (lightweight, fast)
          - "Salesforce/blip-image-captioning-large" (more accurate, slower)
          - "microsoft/git-base" (another good option)
        """
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        logger.info(f"Loading vision model: {model_name} on {self.device}")
        self.captioner = pipeline(
            "image-text-to-text",
            model=model_name,
            device=0 if self.device == "cuda" else -1
        )
        logger.info("Vision model ready")
    
    def take_screenshot(self, region=None):
        """
        Take a screenshot
        
        Args:
            region: Optional tuple (x, y, width, height) for partial screenshot
            
        Returns:
            PIL Image object
        """
        try:
            if region:
                # Partial screenshot
                x, y, w, h = region
                screenshot = pyautogui.screenshot(region=(x, y, w, h))
            else:
                # Full screenshot
                screenshot = pyautogui.screenshot()
            
            logger.info(f"Screenshot taken: {screenshot.size}")
            return screenshot
        
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return None
    
    def save_screenshot(self, filepath="screenshot.png"):
        """Take and save screenshot"""
        try:
            img = self.take_screenshot()
            if img:
                img.save(filepath)
                logger.info(f"Screenshot saved to {filepath}")
                return filepath
        except Exception as e:
            logger.error(f"Save screenshot error: {e}")
        return None
    
    def analyze_image(self, image_path_or_pil):
        """
        Analyze an image and describe what's in it
        
        Args:
            image_path_or_pil: File path (str) or PIL Image object
            
        Returns:
            Description of the image
        """
        try:
            if isinstance(image_path_or_pil, str):
                image = Image.open(image_path_or_pil)
            else:
                image = image_path_or_pil
            
            # Generate caption
            results = self.captioner(image)
            caption = results[0]["generated_text"]
            
            logger.info(f"Image analysis: {caption}")
            return caption
        
        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return "Could not analyze image"
    
    def analyze_current_screen(self):
        """Take screenshot and analyze what's on the screen"""
        try:
            img = self.take_screenshot()
            if img:
                return self.analyze_image(img)
        except Exception as e:
            logger.error(f"Screen analysis error: {e}")
        return "Could not analyze screen"
    
    def find_on_screen(self, description):
        """
        Advanced: Find something on screen based on natural language
        This is a placeholder for more sophisticated vision-based interaction
        """
        # Future: Use object detection or layout analysis
        # For now, just analyze what's there
        return self.analyze_current_screen()