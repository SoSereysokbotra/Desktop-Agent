"""
Local LLM wrapper.

Backend is selectable via the USE_OLLAMA flag below:
  - USE_OLLAMA = True  -> calls Ollama's local HTTP API (default, recommended).
                          Runs a larger model (Qwen2.5-7B) that produces clean
                          JSON tool calls, unlike the 0.5B transformers model.
  - USE_OLLAMA = False -> falls back to the original Hugging Face Transformers
                          path (AutoModelForCausalLM), kept intact for
                          comparison / offline-without-Ollama use.

The PUBLIC INTERFACE is identical across both backends. In particular
`generate(prompt, max_tokens=..., temperature=...)` keeps the same signature
and returns a `str` (returning "Error generating response" on failure), so
planner.py / executor.py / app.py need no changes.
"""

import logging

import requests

logger = logging.getLogger(__name__)

# ─── Backend configuration ──────────────────────────────────────────────────
# Flip USE_OLLAMA to False to fall back to the original transformers backend.
USE_OLLAMA = True

# Ollama HTTP API settings (used when USE_OLLAMA is True)
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"          # instruct-tuned by default in Ollama
OLLAMA_TIMEOUT = 120                 # seconds; a cold 7B load can take ~10s+

# Transformers settings (used when USE_OLLAMA is False)
TRANSFORMERS_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"


class LLM:
    def __init__(self, model_name=None):
        """
        Initialize the LLM backend.

        Args:
            model_name: Optional HuggingFace model ID. Only used by the
                transformers fallback backend. Ignored for Ollama, which uses
                OLLAMA_MODEL. Kept in the signature so existing callers such as
                `LLM()` in app.py continue to work unchanged.
        """
        if USE_OLLAMA:
            self._init_ollama()
        else:
            self._init_transformers(model_name or TRANSFORMERS_MODEL)

    # ------------------------------------------------------------------
    # Backend initialization
    # ------------------------------------------------------------------

    def _init_ollama(self):
        """Initialize the Ollama HTTP backend (no model download, no torch)."""
        self.backend = "ollama"
        self.model_name = OLLAMA_MODEL
        self.device = "ollama"  # informational; keeps attribute present

        logger.info(f"Using Ollama backend: {OLLAMA_MODEL} at {OLLAMA_URL}")

        # Lightweight health check so misconfiguration surfaces at startup
        # rather than on the first user command.
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=5)
            resp.raise_for_status()
            tags = [m.get("name") for m in resp.json().get("models", [])]
            if OLLAMA_MODEL in tags:
                logger.info(f"Ollama reachable; model '{OLLAMA_MODEL}' is available")
            else:
                logger.warning(
                    f"Ollama reachable but model '{OLLAMA_MODEL}' not in {tags}. "
                    f"Run: ollama pull {OLLAMA_MODEL}"
                )
        except Exception as e:
            logger.warning(
                f"Could not reach Ollama at startup ({e}). "
                f"Ensure 'ollama serve' is running."
            )

        logger.info("LLM (Ollama) ready")

    def _init_transformers(self, model_name):
        """
        Initialize the original Hugging Face Transformers backend.

        Preserved verbatim from the pre-Ollama implementation. Torch and
        transformers are imported lazily here so the Ollama path pays no
        import cost and does not require torch to be installed.

        Note: First run downloads ~1.5GB for the 0.5B model. Other options:
          - "Qwen/Qwen2.5-1.5B-Instruct" (larger, more capable)
          - "microsoft/phi-2"
          - "mistralai/Mistral-7B" (if you have the VRAM)
        """
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.backend = "transformers"
        self.model_name = model_name
        self._torch = torch  # stash for use in generate()

        # Detect device
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")

        logger.info(f"Loading model: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, trust_remote_code=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            device_map="auto" if self.device == "cuda" else None,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
        )

        if self.device == "cpu":
            self.model = self.model.to(self.device)

        self.model.eval()
        logger.info("Model loaded successfully")

    # ------------------------------------------------------------------
    # Prompt templates (backend-independent, unchanged)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Generation - single public entry point, identical contract
    # ------------------------------------------------------------------

    def generate(self, prompt, max_tokens=150, temperature=0.7):
        """
        Generate text from a prompt and return a str.

        Signature and return type are IDENTICAL across backends. On any
        failure it logs the error and returns "Error generating response"
        (never raises), matching the original contract that callers rely on.
        """
        if self.backend == "ollama":
            return self._generate_ollama(prompt, max_tokens, temperature)
        return self._generate_transformers(prompt, max_tokens, temperature)

    def _generate_ollama(self, prompt, max_tokens, temperature):
        """Generate via Ollama's /api/generate HTTP endpoint (stream=false)."""
        try:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,  # Ollama's name for max new tokens
                    "temperature": temperature,
                    "top_p": 0.9,
                    "top_k": 50,
                },
            }
            resp = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            return data["response"].strip()

        except Exception as e:
            logger.error(f"Generation error: {e}")
            return "Error generating response"

    def _generate_transformers(self, prompt, max_tokens, temperature):
        """
        Original transformers generation. Decodes only the newly generated
        tokens (after the prompt) to avoid prompt echo. Preserved verbatim.
        """
        try:
            torch = self._torch
            inputs = self.tokenizer.encode(prompt, return_tensors="pt")
            inputs = inputs.to(self.device)
            input_len = inputs.shape[1]

            with torch.no_grad():
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

    # ------------------------------------------------------------------
    # Higher-level helpers (backend-independent, unchanged)
    # ------------------------------------------------------------------

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
            formatted_results = "\n".join(
                [f"- {tool}: {result}" for tool, result in tool_results]
            )
            prompt = self.prompt_template_response(user_message, formatted_results)
        else:
            prompt = self.prompt_template_response(user_message)

        return self.generate(prompt, max_tokens=200, temperature=0.7)
