"""
Website evaluator — Phase 05 + Phase 15 additions.

Takes a business website URL and returns structured signals about its quality.
Uses only httpx (no Playwright) — these are static HTML checks, not JS rendering.

Decision tree (matches the lead scoring rubric in INTEGRATION.md):
  No URL            → skip_ai=True, early_lead_score=10
  Social/Yelp URL   → skip_ai=True, early_lead_score=9
  4xx / 5xx status  → skip_ai=True, early_lead_score=8
  Real website      → extract signals, pass cleaned body text to AI scorer

Phase 15 additions:
  - Expanded directory/booking domain list (Vagaro, Square, Wix,
    OpenTable, DoorDash, etc.) — these were previously mis-scored as
    real sites.
  - Strip <script>/<style>/<!-- comments --> before sending HTML to the
    AI so the snippet reflects visible content, not boilerplate.
  - Email extraction from homepage mailto links + plain-text regex.
  - One additional fetch of /contact /contact-us /about to harvest
    emails and the copyright year the homepage often lacks.
  - Tech-stack fingerprint (Wix, Squarespace, WordPress, Shopify,
    GoDaddy-builder, Webflow, etc.) — tells the outreach pitch what
    migration pain they face.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HTML_SNIPPET_MAX = 3000

# Directory, social, review, booking, and "link-in-bio" sites. A URL
# pointing to any of these is not a real business website — it's a
# placeholder — and should be treated as lead_score = 9.
SOCIAL_DOMAINS: frozenset[str] = frozenset(
    {
        # social
        "facebook.com",
        "fb.com",
        "instagram.com",
        "twitter.com",
        "x.com",
        "linkedin.com",
        "pinterest.com",
        "tiktok.com",
        "youtube.com",
        # review / directory
        "yelp.com",
        "tripadvisor.com",
        "nextdoor.com",
        "thumbtack.com",
        "angieslist.com",
        "houzz.com",
        "bbb.org",
        "mapquest.com",
        "superpages.com",
        "yellowpages.com",
        "manta.com",
        "google.com",
        # booking / delivery / commerce platforms used as a primary "site"
        "opentable.com",
        "doordash.com",
        "ubereats.com",
        "grubhub.com",
        "groupon.com",
        "booksy.com",
        "vagaro.com",
        "styleseat.com",
        "schedulicity.com",
        "setmore.com",
        "calendly.com",
        "etsy.com",
        "shop.app",
        # sitebuilder default domains (owner hasn't bothered with a real domain)
        "wix.com",
        "weebly.com",
        "godaddysites.com",
        "sites.google.com",
        "squareup.com",
        "square.site",
        "linktr.ee",
    }
)

# Copyright patterns scoped to footer first, then full document.
COPYRIGHT_YEAR_PATTERN = re.compile(
    r"(?:©|copyright|\(c\))[^\d]{0,20}((?:19|20)\d{2})", re.IGNORECASE
)
COPYRIGHT_YEAR_FALLBACK = re.compile(r"((?:19|20)\d{2})", re.IGNORECASE)

# Plain-text email regex. Intentionally strict — we only want contact
# addresses, not mangled tracking pixels.
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Emails to ignore (framework defaults, tracking, admin stubs).
EMAIL_DENYLIST_SUBSTRINGS: tuple[str, ...] = (
    "example.com",
    "email@",
    "yourdomain",
    "domain.com",
    "sentry.io",
    "wixpress.com",
    "noreply@",
    "no-reply@",
    "donotreply@",
    "do-not-reply@",
    ".png",
    ".jpg",
    ".gif",
    ".webp",
)

# Tech-stack fingerprint. Key → case-insensitive marker strings we search
# for in the HTML. First match per key wins; multiple tech markers can be
# present (e.g. "wordpress" + "woocommerce").
TECH_MARKERS: dict[str, tuple[str, ...]] = {
    "wix": ("static.parastorage.com", "wix-bolt", "window.wix", "_wix_"),
    "squarespace": (
        "static1.squarespace.com",
        "squarespace-cdn.com",
        "Static.SQUARESPACE_CONTEXT",
    ),
    "wordpress": ("wp-content/", "wp-includes/", "/wp-json/"),
    "woocommerce": ("woocommerce", "wc-ajax"),
    "shopify": ("cdn.shopify.com", "Shopify.theme", "shopify.com/s/"),
    "webflow": ("webflow.com", "wf-form", "data-wf-page"),
    "godaddy-builder": ("cdn.godaddy.com", "mkt.godaddy.com", "websites.godaddy.com"),
    "duda": ("irp.cdn-website.com", "duda-sitebuilder"),
    "joomla": ("/components/com_", "/templates/joomla"),
    "drupal": ("drupal-settings-json", "sites/default/files", "Drupal.settings"),
    "bigcommerce": ("bigcommerce.com/stencil"),
    "framer": ("framerusercontent.com", "framer.com"),
    "react-spa": ('id="root"', '"react"'),
    "nextjs": ("__NEXT_DATA__", "_next/static/"),
    "jquery": ("jquery.js", "jquery.min.js", "jquery-"),
}

# Paths to try for the "contact" follow-up fetch. We stop at the first 2xx.
CONTACT_PATH_CANDIDATES: tuple[str, ...] = (
    "contact",
    "contact-us",
    "contact.html",
    "contacts",
    "about",
    "about-us",
    "reach-us",
    "locations",
)

FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


# ---------------------------------------------------------------------------
# Pure helpers — no I/O.
# ---------------------------------------------------------------------------


def is_social_url(url: str) -> bool:
    """
    Return True if the URL points to a social, directory, booking, or
    placeholder site rather than a real business website.
    """
    if not url:
        return False
    try:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        return any(host == domain or host.endswith("." + domain) for domain in SOCIAL_DOMAINS)
    except Exception:
        return False


def has_mobile_viewport(html: str) -> bool:
    """Return True if the HTML contains a viewport meta tag."""
    return bool(re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.IGNORECASE))


def extract_copyright_year(html: str) -> int | None:
    """
    Scan HTML for a copyright year (e.g. "© 2014", "Copyright 2018").
    Targets the footer area first; falls back to full document.
    """
    footer_match = re.search(r"<footer[^>]*>(.*?)</footer>", html, re.IGNORECASE | re.DOTALL)
    search_text = footer_match.group(1) if footer_match else html

    m = COPYRIGHT_YEAR_PATTERN.search(search_text)
    if m:
        return int(m.group(1))

    if footer_match:
        m = COPYRIGHT_YEAR_FALLBACK.search(search_text)
        if m:
            year = int(m.group(1))
            if 1990 <= year <= 2100:
                return year

    return None


def clean_html_for_ai(html: str, max_chars: int = HTML_SNIPPET_MAX) -> str:
    """
    Produce a compact, AI-friendly snippet of the page's visible content.

    Strips <script>, <style>, HTML comments, and collapses whitespace. The
    raw first 3000 chars of most modern sites are a wasteland of inline
    styles and framework bootstrap — this gives the AI real content to
    evaluate (headings, nav, hero copy, footer).
    """
    if not html:
        return ""

    # Strip scripts, styles, comments, <noscript>
    cleaned = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<style\b[^>]*>.*?</style>", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<!--.*?-->", " ", cleaned, flags=re.DOTALL)
    cleaned = re.sub(
        r"<noscript\b[^>]*>.*?</noscript>",
        " ",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Collapse whitespace *between* tags so tags still present remain
    # visible markers for the AI (it uses tag names to reason about structure).
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars]


def extract_emails(html: str) -> list[str]:
    """
    Extract candidate contact emails from HTML.

    Scans mailto: links first (highest quality), then plain text. De-dupes
    and filters the obvious junk (framework defaults, noreply, image names
    that happen to contain @).
    """
    if not html:
        return []

    found: list[str] = []
    seen: set[str] = set()

    # 1) mailto: links — the intended contact channel.
    for m in re.finditer(r'mailto:([^"\'<>?\s]+)', html, re.IGNORECASE):
        email = m.group(1).strip().lower()
        if _is_valid_email(email) and email not in seen:
            seen.add(email)
            found.append(email)

    # 2) plain-text email regex across the body.
    for m in EMAIL_PATTERN.finditer(html):
        email = m.group(0).strip().lower()
        if _is_valid_email(email) and email not in seen:
            seen.add(email)
            found.append(email)

    return found


def _is_valid_email(email: str) -> bool:
    """True if the candidate email looks usable for outreach."""
    if not email or "@" not in email:
        return False
    if any(marker in email for marker in EMAIL_DENYLIST_SUBSTRINGS):
        return False
    if len(email) > 100:
        return False
    return True


def detect_tech_stack(html: str) -> list[str]:
    """
    Detect builder/CMS/framework markers in HTML.

    Returns a list of lowercase keys from `TECH_MARKERS` that appeared at
    least once. Preserves insertion order. Empty list if nothing matched.
    """
    if not html:
        return []
    lower = html.lower()
    hits: list[str] = []
    for tech, markers in TECH_MARKERS.items():
        for marker in markers:
            if marker.lower() in lower:
                hits.append(tech)
                break
    return hits


def build_early_result(
    url: str | None,
    early_lead_score: int,
    status_code: int | None = None,
) -> dict:
    """Build the standard result dict for cases where AI scoring is skipped."""
    return {
        "website_url": url,
        "website_status_code": status_code,
        "has_ssl": None,
        "has_mobile_viewport": None,
        "copyright_year": None,
        "email": None,
        "tech_stack": [],
        "html_snippet": None,
        "skip_ai": True,
        "early_lead_score": early_lead_score,
    }


def build_full_result(
    url: str,
    status_code: int,
    html: str,
    extra_html: str = "",
) -> dict:
    """
    Build the result dict for a real website that passes to AI scoring.

    `extra_html` is any supplementary HTML (contact/about page) used for
    email + copyright extraction but NOT passed to the AI scorer.
    """
    combined = html + "\n" + extra_html
    emails = extract_emails(combined)

    return {
        "website_url": url,
        "website_status_code": status_code,
        "has_ssl": url.startswith("https://"),
        "has_mobile_viewport": has_mobile_viewport(html),
        # Prefer a copyright year from the extra (contact) page if homepage
        # lacks one — contact pages are often simpler and expose the footer.
        "copyright_year": extract_copyright_year(html) or extract_copyright_year(extra_html),
        "email": emails[0] if emails else None,
        "tech_stack": detect_tech_stack(combined),
        "html_snippet": clean_html_for_ai(html),
        "skip_ai": False,
        "early_lead_score": None,
    }


# ---------------------------------------------------------------------------
# HTTP fetching (with tenacity retry)
# ---------------------------------------------------------------------------


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=6),
    reraise=True,
)
async def _fetch(url: str, timeout: float = 10.0) -> httpx.Response:
    """Fetch a URL, following redirects. Retries on timeout or connection error."""
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers=FETCH_HEADERS,
    ) as client:
        return await client.get(url)


async def _fetch_contact_page(base_url: str, html: str) -> str:
    """
    Try to fetch a contact/about page to harvest extra emails.

    Strategy:
      1) Prefer an explicit <a href="…contact…"> from the homepage.
      2) Otherwise try common paths (`/contact`, `/about`, …).

    Short 6s timeout, single attempt each — this is best-effort.
    """
    candidates: list[str] = []

    # 1) Explicit link in homepage HTML
    for m in re.finditer(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>[^<]*'
        r"(?:contact|reach\s+us|get\s+in\s+touch)[^<]*</a>",
        html,
        re.IGNORECASE,
    ):
        candidates.append(urljoin(base_url, m.group(1)))

    # 2) Standard paths
    for path in CONTACT_PATH_CANDIDATES:
        candidates.append(urljoin(base_url.rstrip("/") + "/", path))

    # De-dupe while preserving order, cap at 4 tries so we don't thrash.
    seen: set[str] = set()
    unique: list[str] = []
    for url in candidates:
        if url not in seen and url != base_url:
            seen.add(url)
            unique.append(url)
        if len(unique) >= 4:
            break

    for url in unique:
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=6.0,
                headers=FETCH_HEADERS,
            ) as client:
                resp = await client.get(url)
            if resp.status_code < 400 and resp.text:
                logger.debug(f"Contact page found: {url}")
                return resp.text
        except Exception:
            continue

    return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def evaluate_website(url: str | None) -> dict:
    """
    Evaluate a business website URL and return a structured signal dict.

    The returned dict always has the same keys regardless of which path
    was taken — callers can rely on the shape unconditionally.
    """
    # --- No URL ---
    if not url or not url.strip():
        logger.debug("No website URL — score 10.")
        return build_early_result(url=None, early_lead_score=10)

    url = url.strip()

    # --- Social / directory URL ---
    if is_social_url(url):
        logger.debug(f"Social/directory URL: {url} — score 9.")
        return build_early_result(url=url, early_lead_score=9)

    # --- Ensure scheme ---
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # --- Fetch the homepage ---
    try:
        response = await _fetch(url)
    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching {url} — score 8.")
        return build_early_result(url=url, early_lead_score=8, status_code=None)
    except httpx.ConnectError as e:
        logger.warning(f"Connection error fetching {url}: {e} — score 8.")
        return build_early_result(url=url, early_lead_score=8, status_code=None)
    except Exception as e:
        logger.warning(f"Unexpected error fetching {url}: {e} — score 8.")
        return build_early_result(url=url, early_lead_score=8, status_code=None)

    status = response.status_code

    # --- 4xx / 5xx response ---
    if status >= 400:
        logger.debug(f"HTTP {status} from {url} — score 8.")
        return build_early_result(url=url, early_lead_score=8, status_code=status)

    # --- Real website — extract signals ---
    final_url = str(response.url)
    html = response.text

    # Try one contact-page fetch for extra email/copyright signals.
    extra_html = await _fetch_contact_page(final_url, html)

    logger.debug(f"Live website: {final_url} (HTTP {status}) — passing to AI scorer.")
    return build_full_result(url=final_url, status_code=status, html=html, extra_html=extra_html)
