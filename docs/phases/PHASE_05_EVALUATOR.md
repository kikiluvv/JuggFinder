# Phase 05 — Website Evaluator

## Goal
For each business record returned by the scraper, evaluate the quality of its website using `httpx` (no browser). Extract structured signals used by the scorer in the next phase.

## Completion Criteria
- [ ] `evaluate_website(url: str | None) -> dict` returns a consistent result shape for all input cases
- [ ] Handles: no URL, social/Yelp URL, 4xx/5xx response, and real websites
- [ ] Checks: HTTPS, mobile viewport meta tag, copyright year in footer, HTTP status code
- [ ] Returns raw HTML snippet (≤ 3000 chars) for AI scoring in Phase 06
- [ ] Uses `tenacity` for retries on transient network errors
- [ ] Never uses Playwright — only `httpx`

---

## File: `src/scraper/evaluator.py`

### Output shape (dict)

```python
{
    "website_url": str | None,
    "website_status_code": int | None,
    "has_ssl": bool | None,
    "has_mobile_viewport": bool | None,
    "copyright_year": int | None,
    "html_snippet": str | None,   # first 3000 chars of body text, for AI
    "skip_ai": bool,              # True if no URL / social / error status
    "early_lead_score": int | None,  # set if skip_ai is True (10, 9, or 8)
}
```

### Decision tree (matches the rubric in `INTEGRATION.md`)

```
No URL?
  → skip_ai=True, early_lead_score=10, return immediately

URL is social/Yelp?
  (check: "facebook.com", "yelp.com", "instagram.com", "google.com/maps")
  → skip_ai=True, early_lead_score=9, return immediately

Fetch URL with httpx (follow redirects, timeout=10s):
  Status 4xx or 5xx?
    → skip_ai=True, early_lead_score=8, return immediately

  Status 2xx/3xx:
    → has_ssl = url.startswith("https://")
    → has_mobile_viewport = '<meta name="viewport"' in html (case-insensitive)
    → copyright_year = extract 4-digit year from footer text (regex)
    → html_snippet = first 3000 chars of response text
    → skip_ai=False, early_lead_score=None
```

### Social URL detection helper

```python
SOCIAL_DOMAINS = {"facebook.com", "fb.com", "yelp.com", "instagram.com",
                   "twitter.com", "x.com", "google.com"}

def is_social_url(url: str) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url).netloc.lower().lstrip("www.")
    return any(host == d or host.endswith("." + d) for d in SOCIAL_DOMAINS)
```

### Retry config (tenacity)

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=6),
)
async def fetch_url(url: str) -> httpx.Response:
    async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
        return await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
```

---

## Done When
`evaluate_website(None)` returns `early_lead_score=10`. `evaluate_website("https://facebook.com/somebiz")` returns `early_lead_score=9`. `evaluate_website("https://realsite.com")` returns `skip_ai=False` with HTML snippet and signal booleans populated.
