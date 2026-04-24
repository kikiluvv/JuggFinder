# Phase 06 — AI Scoring

## Goal
Send the HTML snippet from the evaluator to Gemini 1.5 Flash for a website quality score. Fall back to Groq Llama 3 on rate limit errors. Store `null` values if both fail — never block the pipeline.

## Completion Criteria
- [ ] `score_with_ai(html_snippet: str) -> dict` returns `{score, issues, summary}` or null equivalents
- [ ] Uses Gemini 1.5 Flash as primary
- [ ] Switches to Groq Llama 3 8B on `429` (for remainder of session, not just one call)
- [ ] If both fail: returns `{score: None, issues: [], summary: None}` and logs the error
- [ ] Parses the JSON response safely (handles malformed responses without crashing)
- [ ] The prompt matches the template in `INTEGRATION.md` exactly

---

## File: `src/scorer/ai.py`

### Session-level fallback state

Use a module-level flag to track whether the session has already switched to Groq:

```python
_use_groq_fallback: bool = False
```

Once Gemini fails with a 429, set `_use_groq_fallback = True`. All subsequent calls in the same scrape session go to Groq directly.

### Prompt template

```python
PROMPT_TEMPLATE = """
You are evaluating a small business website to determine if it needs a professional redesign.
Analyze the following HTML content and return ONLY a valid JSON object — no explanation, no markdown.

HTML snippet (truncated to 3000 chars):
{html_snippet}

Respond with exactly this JSON format:
{{
  "score": <integer 1-10>,
  "issues": ["<issue1>", "<issue2>", ...],
  "summary": "<one sentence describing the website quality>"
}}

Scoring guide:
10 = modern, fast, mobile-friendly, professional design
 7 = functional but visually dated or lacking polish
 5 = clearly outdated, not mobile-friendly, or unprofessional
 3 = barely functional, very old design
 1 = broken, nearly non-existent, or completely unusable
"""
```

### Gemini call

```python
import google.generativeai as genai
from src.config.settings import settings

genai.configure(api_key=settings.gemini_api_key)
_gemini_model = genai.GenerativeModel("gemini-1.5-flash")

async def _call_gemini(html_snippet: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(html_snippet=html_snippet[:3000])
    response = await asyncio.to_thread(_gemini_model.generate_content, prompt)
    return _parse_ai_response(response.text)
```

> Note: `google-generativeai` is synchronous — wrap with `asyncio.to_thread`.

### Groq call

```python
from groq import Groq

_groq_client = Groq(api_key=settings.groq_api_key)

async def _call_groq(html_snippet: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(html_snippet=html_snippet[:3000])
    response = await asyncio.to_thread(
        _groq_client.chat.completions.create,
        model="llama3-8b-8192",
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_ai_response(response.choices[0].message.content)
```

### Safe JSON parser

```python
import json, re

def _parse_ai_response(text: str) -> dict:
    try:
        # Strip markdown fences if present
        clean = re.sub(r"```(?:json)?|```", "", text).strip()
        data = json.loads(clean)
        return {
            "score": int(data.get("score", 0)) or None,
            "issues": data.get("issues", []),
            "summary": data.get("summary"),
        }
    except Exception:
        return {"score": None, "issues": [], "summary": None}
```

### Main entry point with fallback logic

```python
async def score_with_ai(html_snippet: str) -> dict:
    global _use_groq_fallback
    null_result = {"score": None, "issues": [], "summary": None}

    if not _use_groq_fallback:
        try:
            return await _call_gemini(html_snippet)
        except Exception as e:
            if "429" in str(e) or "ResourceExhausted" in str(e):
                logger.warning("Gemini rate limited — switching to Groq for this session")
                _use_groq_fallback = True
            else:
                logger.error(f"Gemini error: {e}")
                return null_result

    # Groq path
    try:
        return await _call_groq(html_snippet)
    except Exception as e:
        logger.error(f"Groq error: {e}")
        return null_result
```

---

## Done When
Calling `score_with_ai(some_html)` returns a dict with `score` (int or None), `issues` (list), `summary` (str or None). Passing garbage HTML does not crash — it returns null equivalents.
