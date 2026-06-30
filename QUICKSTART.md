# Quick Start (5 Minutes)

## Install

```bash
# 1. Create virtual env
python -m venv venv

# 2. Activate (Windows)
venv\Scripts\activate

# 3. Install packages
pip install -r requirements.txt
```

**⏱️ This takes ~2-3 minutes**

## Run

```bash
python app.py
```

**First run:** Will download models (~2GB). Wait 10-30 seconds.
**Subsequent runs:** Instant.

## Try These Commands

Once you see the `You:` prompt:

```
Open notepad
Take a screenshot
What's on my screen?
Press enter
Click center
Type hello
Open calculator
Close calculator
```

## That's It!

You now have a desktop AI agent.

## Next Steps

1. **Read README.md** - Full setup + options
2. **Read EXTENDING.md** - How to add new tools
3. **Start adding tools** - Follow the examples
4. **Build V4** - Add file operations, web tools, etc.

---

## If Stuck

### Error: "Module not found"
Make sure `venv\Scripts\activate` was run

### Error: "GPU out of memory"
Edit `models/llm.py` line 14:
```python
model_name="microsoft/phi-2"  # Smaller model
```

### Model download fails
```bash
# Manually download model
python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('Qwen/Qwen2.5-0.5B-Instruct')"
```

### Agent doesn't understand my command
Try simpler commands like `"Open notepad"` first

---

**Ready?** Run `python app.py`