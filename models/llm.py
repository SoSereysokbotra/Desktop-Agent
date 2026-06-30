"""
Local LLM wrapper using Hugging Face Transformers
Uses Qwen 0.5B-1B (runs efficiently on Windows)
"""

import logging
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

logger = logging.getLogger(__name__)


class LLM:
    def __init__(self, model_name="Qwen/Qwen2.5-0.5B-Instruct"):
        """
        Initialize local LLM
        
        Args:
            model_name: HuggingFace model ID
            
        Note: First run downloads ~1.5GB for 0.5B model
        You can also use:
          - "Qwen/Qwen2.5-1.5B-Instruct" (larger, more capable)
          - "microsoft/phi-2" (another good option)
          - "mistralai/Mistral-7B" (if you have the VRAM)
        """
        self.model_name = model_name
        
        # Detect device
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")
        
        logger.info(f"Loading model: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            device_map="auto" if self.device == "cuda" else None,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
        )
        
        if self.device == "cpu":
            self.model = self.model.to(self.device)
        
        self.model.eval()
        logger.info("Model loaded successfully")
    
    def prompt_template_agent(self, user_message, system_prompt=""):
        """Format message for agent decision-making"""
        if not system_prompt:
            system_prompt = """You are an AI desktop assistant. You can control Windows, open applications, 
take screenshots, and interact with files. When the user asks you to do something, decide:
1. Can I answer this directly? (general questions, explanations)
2. Do I need to use tools? (open app, take screenshot, interact with desktop)

If tools are needed, respond ONLY with:
TOOLS_NEEDED: <comma-separated list of tool names>

If you can answer directly, just respond naturally."""
        
        return f"""<|im_start|>system
{system_prompt}
<|im_end|>
<|im_start|>user
{user_message}
<|im_end|>
<|im_start|>assistant"""
    
    def prompt_template_response(self, user_message, tool_results=""):
        """Format message for natural response after tool execution"""
        context = ""
        if tool_results:
            context = f"\n\nThe requested tool has already been executed.\n\nTool Results:\n{tool_results}\n"
        
        system_prompt = "You are a helpful AI desktop assistant. Respond naturally to the user explaining what happened based on the tool results."
        
        return f"""<|im_start|>system
{system_prompt}
<|im_end|>
<|im_start|>user
The user asked: "{user_message}"{context}
<|im_end|>
<|im_start|>assistant"""
    
    def generate(self, prompt, max_tokens=150, temperature=0.7):
        """Generate text from prompt, decoding only the newly generated tokens."""
        try:
            inputs = self.tokenizer.encode(prompt, return_tensors="pt")
            inputs = inputs.to(self.device)
            input_len = inputs.shape[1]

            outputs = self.model.generate(
                inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=0.9,
                top_k=50,
                eos_token_id=self.tokenizer.eos_token_id,
            )

            # Decode only the new tokens (after the prompt) to avoid prompt echo
            new_tokens = outputs[0][input_len:]
            response = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
            return response.strip()

        except Exception as e:
            logger.error(f"Generation error: {e}")
            return "Error generating response"
    
    def should_use_tools(self, user_message):
        """Ask LLM: do we need tools for this request?"""
        prompt = self.prompt_template_agent(user_message)
        response = self.generate(prompt, max_tokens=50)
        
        return "TOOLS_NEEDED:" in response
    
    def extract_tool_names(self, user_message):
        """Extract which tools the LLM wants to use"""
        prompt = self.prompt_template_agent(user_message)
        response = self.generate(prompt, max_tokens=100)
        
        if "TOOLS_NEEDED:" in response:
            tools_str = response.split("TOOLS_NEEDED:")[-1].strip()
            tools = [t.strip() for t in tools_str.split(",")]
            return tools
        return []
    
    def generate_response(self, user_message, tool_results=""):
        """Generate a natural response"""
        if tool_results:
            formatted_results = "\n".join([f"- {tool}: {result}" for tool, result in tool_results])
            prompt = self.prompt_template_response(user_message, formatted_results)
        else:
            prompt = self.prompt_template_response(user_message)
        
        return self.generate(prompt, max_tokens=200, temperature=0.7)