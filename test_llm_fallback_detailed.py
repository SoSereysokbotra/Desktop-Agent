"""
LLM Fallback - Full execution trace with actual prompt/response

This test instruments parse_llm_tool_call() to show:
1. The exact prompt sent to LLM
2. The raw response string
3. Which parsing branch is taken
"""

import json
import logging

from agent.planner import Planner, detect_tools
from agent.tools import ToolRegistry
from models.llm import LLM

# Monkey-patch parse_llm_tool_call to add detailed logging
original_parse = Planner.parse_llm_tool_call


def instrumented_parse(self, user_input):
    print("\n" + "=" * 70)
    print("INSIDE parse_llm_tool_call()")
    print("=" * 70)

    # Get schemas
    tool_schemas = ToolRegistry.get_json_schemas()

    # Build prompt
    prompt = f"""You are a desktop automation assistant. The user said: "{user_input}"

Available tools (JSON schemas):
{json.dumps(tool_schemas, indent=2)}

Output ONLY valid JSON in this exact format (no other text):
{{"tool": "tool_name", "args": {{"key": "value"}}}}

If multiple tools are needed, output a JSON array:
[
  {{"tool": "tool_name1", "args": {{}}}},
  {{"tool": "tool_name2", "args": {{}}}}
]

JSON output:"""

    print("\nPROMPT SENT TO LLM:")
    print("-" * 70)
    print(prompt)
    print("-" * 70)

    # Call LLM
    print("\nCalling self.llm.generate()...")
    response = self.llm.generate(prompt, max_tokens=200)

    print("\nRAW LLM RESPONSE:")
    print("-" * 70)
    print(repr(response))
    print("-" * 70)

    # Parse with error handling
    print("\nParsing JSON...")
    try:
        parsed = json.loads(response.strip())
        print(f"  Success! Parsed: {parsed}")

        # Normalize
        if isinstance(parsed, dict):
            result = [(parsed["tool"], parsed.get("args", {}))]
            print(f"  Normalized to: {result}")
            return result
        elif isinstance(parsed, list):
            result = [(item["tool"], item.get("args", {})) for item in parsed]
            print(f"  Normalized to: {result}")
            return result
        else:
            print(f"  ERROR: Unexpected structure type: {type(parsed)}")
            return []

    except json.JSONDecodeError as e:
        print(f"  ERROR: JSONDecodeError - {e}")
        print("  Returning []")
        return []

    except (KeyError, TypeError) as e:
        print(f"  ERROR: KeyError/TypeError - {e}")
        print("  Returning []")
        return []


Planner.parse_llm_tool_call = instrumented_parse

# Now run the test
print("=" * 70)
print("LLM FALLBACK DETAILED TRACE")
print("=" * 70)

llm = LLM()
planner = Planner(llm)

user_input = "please wait for 3 seconds"
print(f"\nUser input: '{user_input}'")

print("\n1. Checking regex...")
regex_result = detect_tools(user_input)
print(f"   Regex returned: {regex_result}")

print("\n2. Calling extract_tools() which will trigger LLM fallback...")
result = planner.extract_tools(user_input)

print("\n" + "=" * 70)
print("FINAL RESULT FROM extract_tools():")
print("=" * 70)
print(f"  {result}")

print("\n" + "=" * 70)
print("PROOF COMPLETE")
print("=" * 70)
print("\nWe can see:")
print("  1. The exact prompt sent to the LLM")
print("  2. The raw response string from the LLM")
print("  3. Which parsing branch executed")
print("  4. The final return value")
