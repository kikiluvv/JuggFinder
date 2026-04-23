"""
Google Maps scraper using Playwright.

Strategy:
  Phase 1 — Scroll the search results feed to collect all place card URLs.
  Phase 2 — Navigate to each place URL individually and extract full details.

Hardening (Phase 15):
  - New-headless mode ("new") toggle via settings.
  - Modern Chromium context (locale, timezone, viewport, geolocation,
    permissions) set per session so we look like a regular Boise visitor.
  - Stealth init-script hides `navigator.webdriver`, spoofs `languages`,
    `plugins`, and `chrome.runtime` — shuts down the cheapest bot checks.
  - User-agent rotation: pool of current Chrome/Safari/Firefox UAs,
    overridable via SCRAPE_USER_AGENT.
  - CAPTCHA / "sorry" page detection raises a loud error so the pipeline
    surfaces it in logs and the API status.
  - Selector-health counters track what we actually extracted per run
    (consumed by the pipeline for drift detection).
  - Additional field extraction: hours, google_categories, photo_count,
    is_claimed, business_description.
"""

from __future__ import annotations

import asyncio
import random
import re
from dataclasses import dataclass, field
from urllib.parse import quote_plus

from playwright.async_api import Browser, BrowserContext, Page
from playwright.async_api import TimeoutError as PlaywrightTimeout
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config.settings import settings
from src.db.models import Lead
from src.utils.logging import get_logger

logger = get_logger(__name__)

# --- Constants ---
SCROLL_PAUSE_MIN = 2.0
SCROLL_PAUSE_MAX = 4.0
MAX_STALE_SCROLLS = 6  # bumped from 4 to tolerate slow lazy loads

# Curated pool of up-to-date user agents. Rotated per run unless
# SCRAPE_USER_AGENT is set in the env.
USER_AGENT_POOL: list[str] = [
    # Chrome 131 on macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    # Chrome 131 on Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    # Safari 17 on macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.6 Safari/605.1.15"
    ),
    # Firefox 132 on macOS
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0"),
]

# Boise, Idaho — seed geolocation for the Chromium context. Maps tailors
# ranking to viewer location; matching the search query removes one more
# "you're not who you say you are" tell.
BOISE_GEOLOCATION = {"latitude": 43.6150, "longitude": -116.2023}

# Stealth init-script — runs before any page JS. Shuts down the three
# cheapest headless-detection vectors.
STEALTH_SCRIPT = """
// Hide webdriver flag
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// Populate plugins (empty array is a giveaway)
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5].map(() => ({ name: 'Chrome PDF Plugin' })),
});

// Populate languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
});

// chrome.runtime stub (present in headed Chrome, absent in old headless)
if (!window.chrome) { window.chrome = {}; }
if (!window.chrome.runtime) { window.chrome.runtime = {}; }

// Notification permission query — some detectors poll this
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters)
    );
}
"""

# --- Selector banks (ordered by reliability; first match wins) ---
FEED_SELECTORS = [
    "div[role='feed']",
    "div.m6QErb[aria-label]",
    "div.m6QErb",
]
CARD_SELECTOR = "a.hfpxzc"
CARD_FALLBACK = "a[href*='/maps/place/']"

NAME_SELECTORS = [
    "h1.DUwDvf",
    "h1[class*='fontHeadlineLarge']",
    "h1",
]
ADDRESS_SELECTORS = [
    "button[data-item-id='address'] .Io6YTe",
    "button[data-item-id='address']",
    "[data-tooltip='Copy address'] .Io6YTe",
    "button[aria-label*='ddress'] .Io6YTe",
]
PHONE_SELECTORS = [
    "button[data-item-id*='phone'] .Io6YTe",
    "button[data-item-id*='phone:tel'] .Io6YTe",
    "button[aria-label*='hone'] .Io6YTe",
]
WEBSITE_SELECTORS = [
    "a[data-item-id='authority']",
    "a[aria-label*='website' i]",
    "a[href]:not([href*='google']):not([href*='maps'])[data-item-id]",
]
RATING_SELECTORS = [
    "div.F7nice > span[aria-hidden='true']",
    "span.ceNzKf[aria-label*='star']",
    "div.F7nice span",
]
REVIEW_SELECTORS = [
    "div.F7nice span[aria-label*='review']",
    "button[aria-label*='review']",
    "span[aria-label*='review']",
]
CONSENT_SELECTORS = [
    "button[aria-label*='Accept all' i]",
    "button[aria-label*='Reject all' i]",
    "form[action*='consent'] button",
    "#L2AGLb",
    "button.tHlp8d",
]

# --- New field selectors (Phase 15) ---
# Google category chip just below the business name.
CATEGORY_SELECTORS = [
    "button.DkEaL",
    "button[jsaction*='category']",
    "div.LBgpqf button",
]
# Hours button in the side panel. Text is like "Open ⋅ Closes 10 PM".
HOURS_SELECTORS = [
    "div[aria-label*='hours' i]",
    "button[data-item-id='oh'] .Io6YTe",
    "button[aria-label*='hours' i]",
]
# Editorial description near the top of the place panel.
DESCRIPTION_SELECTORS = [
    "div.PYvSYb",
    "div.bJzME .WeS02d",
    "div[class*='description']",
]
# "N photos" button in the photo tab.
PHOTO_COUNT_SELECTORS = [
    "button[aria-label*='photo' i] .fontTitleSmall",
    "div.aoRNLd button[aria-label*='photo' i]",
    "button[aria-label*='photo' i]",
]
# "Claim this business" link appears only when the listing is unclaimed.
CLAIM_SELECTORS = [
    "a[aria-label*='Claim this business' i]",
    "a[href*='claim']",
    "button[aria-label*='Claim this business' i]",
]

# End-of-results markers Google shows when there are no more listings
END_OF_RESULTS_TEXTS = [
    "you've reached the end",
    "no more results",
]

# CAPTCHA / rate-limit page fingerprints. Any match → abort the run.
CAPTCHA_URL_MARKERS = ("/sorry/", "google.com/sorry", "consent.google.com/sorry")
CAPTCHA_BODY_MARKERS = (
    "unusual traffic from your computer network",
    "to continue, please type the characters",
    "our systems have detected unusual traffic",
)


class CaptchaEncountered(Exception):
    """Raised when Google serves a CAPTCHA / 'unusual traffic' page."""


# ---------------------------------------------------------------------------
# Selector-health counters (shared with the pipeline)
# ---------------------------------------------------------------------------


@dataclass
class SelectorHealth:
    """Counts successful extractions per field across a full scrape run."""

    cards_found: int = 0
    names_extracted: int = 0
    addresses_extracted: int = 0
    phones_extracted: int = 0
    websites_extracted: int = 0
    ratings_extracted: int = 0
    reviews_extracted: int = 0
    categories_extracted: int = 0
    hours_extracted: int = 0
    descriptions_extracted: int = 0
    captchas_encountered: int = 0
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "cards_found": self.cards_found,
            "names_extracted": self.names_extracted,
            "addresses_extracted": self.addresses_extracted,
            "phones_extracted": self.phones_extracted,
            "websites_extracted": self.websites_extracted,
            "ratings_extracted": self.ratings_extracted,
            "reviews_extracted": self.reviews_extracted,
            "categories_extracted": self.categories_extracted,
            "hours_extracted": self.hours_extracted,
            "descriptions_extracted": self.descriptions_extracted,
            "captchas_encountered": self.captchas_encountered,
            "failures": list(self.failures[-5:]),  # keep only recent 5
        }


# ---------------------------------------------------------------------------
# Pure helper functions — no I/O, fully unit-testable.
# ---------------------------------------------------------------------------


def pick_user_agent() -> str:
    """Return the configured UA if set, else a random member of the pool."""
    if settings.scrape_user_agent.strip():
        return settings.scrape_user_agent.strip()
    return random.choice(USER_AGENT_POOL)


def build_search_url(category: str, location: str | None = None) -> str:
    """Build a Google Maps search URL for a category in a location."""
    loc = location or settings.scrape_location
    query = f"{category} {loc}"
    return f"https://www.google.com/maps/search/{quote_plus(query)}"


def extract_place_id_from_url(url: str) -> str | None:
    """
    Extract the Google Maps place ID from a place detail URL.

    Handles three formats: legacy hex (0x…), ChIJ (rolled out 2020+), and
    GhIJ (newer experimental variant). Place IDs live in the `data` path
    segment as `!1s{place_id}!`.
    """
    for pattern in (
        r"!1s(ChIJ[^!&\s]+)",
        r"!1s(GhIJ[^!&\s]+)",
        r"!1s(0x[0-9a-fA-F]+:[0-9a-fA-Fx]+)",
    ):
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def parse_rating(text: str) -> float | None:
    """
    Extract a star rating from a text string.

    Handles formats like '4.5', '4.5 stars', '4,5' (European decimal).
    Returns None if no valid rating in (0, 5] is found.
    """
    normalized = text.replace(",", ".")
    m = re.search(r"(\d+\.?\d*)", normalized)
    if m:
        try:
            val = float(m.group(1))
            if 0 < val <= 5:
                return val
        except ValueError:
            pass
    return None


def parse_review_count(text: str) -> int | None:
    """
    Extract an integer review count from a text string.

    Handles '(123)', '1,234 reviews', '1.2K reviews'.
    """
    k_match = re.search(r"(\d+\.?\d*)[Kk]", text)
    if k_match:
        return int(float(k_match.group(1)) * 1000)

    cleaned = text.replace(",", "")
    m = re.search(r"(\d+)", cleaned)
    if m:
        return int(m.group(1))
    return None


def parse_photo_count(text: str) -> int | None:
    """Extract a photo count from labels like 'See photos', '124 photos', '3.2K'."""
    return parse_review_count(text)


def is_end_of_results(text: str) -> bool:
    """Return True if the text signals there are no more results to scroll."""
    lower = text.lower()
    return any(marker in lower for marker in END_OF_RESULTS_TEXTS)


def is_captcha_page(url: str, body_sample: str) -> bool:
    """
    Return True if the current page looks like Google's CAPTCHA / sorry
    interstitial. Checks URL markers first (cheap), then body text.
    """
    lower_url = url.lower()
    if any(marker in lower_url for marker in CAPTCHA_URL_MARKERS):
        return True
    lower_body = body_sample.lower()
    return any(marker in lower_body for marker in CAPTCHA_BODY_MARKERS)


# ---------------------------------------------------------------------------
# Playwright helpers
# ---------------------------------------------------------------------------


async def build_context(browser: Browser) -> BrowserContext:
    """
    Build a Chromium context configured to look like a normal Boise visitor.

    Sets UA, locale, timezone, viewport, geolocation, and installs the
    stealth init-script. Call once per scrape run and reuse across pages.
    """
    user_agent = pick_user_agent()
    context = await browser.new_context(
        user_agent=user_agent,
        locale="en-US",
        timezone_id="America/Boise",
        viewport={"width": 1440, "height": 900},
        geolocation=BOISE_GEOLOCATION,
        permissions=["geolocation"],
    )
    await context.add_init_script(STEALTH_SCRIPT)
    logger.debug(f"Context built — UA: {user_agent[:60]}…")
    return context


@retry(
    retry=retry_if_exception_type(PlaywrightTimeout),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def _navigate(page: Page, url: str) -> None:
    """Navigate to a URL, retrying up to 3 times on timeout."""
    await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
    # Brief pause for JS-rendered content to settle
    await asyncio.sleep(1.5)


async def _check_captcha(page: Page) -> None:
    """
    Raise CaptchaEncountered if the page is Google's CAPTCHA interstitial.

    Reads a short body snippet — full page.content() would be wasteful and
    could itself trigger the interstitial's JS.
    """
    try:
        body = await page.locator("body").inner_text(timeout=1_000)
    except Exception:
        body = ""
    if is_captcha_page(page.url, body[:500]):
        raise CaptchaEncountered(f"CAPTCHA / 'unusual traffic' page at: {page.url}")


async def _handle_consent(page: Page) -> None:
    """Dismiss Google's GDPR/cookie consent dialog if it appears."""
    for selector in CONSENT_SELECTORS:
        try:
            btn = await page.query_selector(selector)
            if btn and await btn.is_visible():
                await btn.click()
                await asyncio.sleep(1.0)
                logger.debug("Dismissed consent dialog.")
                return
        except Exception:
            continue


async def _get_text(page: Page, selectors: list[str]) -> str | None:
    """Return inner text from the first matching selector, or None."""
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text:
                    return text
        except Exception:
            continue
    return None


async def _get_href(page: Page, selectors: list[str]) -> str | None:
    """Return the href attribute from the first matching selector, or None."""
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                href = await el.get_attribute("href")
                if href:
                    return href.strip()
        except Exception:
            continue
    return None


async def _get_all_texts(page: Page, selectors: list[str], limit: int = 5) -> list[str]:
    """
    Return up to `limit` unique non-empty inner texts across the first
    selector that produces any matches.
    """
    for sel in selectors:
        try:
            els = await page.query_selector_all(sel)
            if not els:
                continue
            results: list[str] = []
            seen: set[str] = set()
            for el in els:
                try:
                    t = (await el.inner_text()).strip()
                except Exception:
                    continue
                if t and t not in seen:
                    seen.add(t)
                    results.append(t)
                    if len(results) >= limit:
                        break
            if results:
                return results
        except Exception:
            continue
    return []


async def _collect_card_hrefs(
    page: Page,
    search_url: str,
    max_results: int,
    health: SelectorHealth,
) -> list[str]:
    """
    Navigate to the Maps search URL and scroll the results feed to collect
    all place card hrefs up to `max_results`.
    """
    try:
        await _navigate(page, search_url)
    except PlaywrightTimeout:
        logger.error(f"Timed out loading search results: {search_url}")
        return []

    # CAPTCHA check — if we landed on a sorry page, abort the whole run.
    await _check_captcha(page)
    await _handle_consent(page)

    # Locate the scrollable results feed
    feed_el = None
    for sel in FEED_SELECTORS:
        try:
            feed_el = await page.wait_for_selector(sel, timeout=10_000)
            if feed_el:
                logger.debug(f"Found feed with selector: {sel}")
                break
        except PlaywrightTimeout:
            continue

    if not feed_el:
        logger.warning(f"No results feed found for: {search_url}")
        health.failures.append(f"feed-missing:{search_url}")
        return []

    hrefs: list[str] = []
    seen: set[str] = set()
    stale_scrolls = 0

    while len(hrefs) < max_results and stale_scrolls < MAX_STALE_SCROLLS:
        cards = []
        for selector in (CARD_SELECTOR, CARD_FALLBACK):
            cards = await page.query_selector_all(selector)
            if cards:
                break

        prev_count = len(hrefs)
        for card in cards:
            try:
                href = await card.get_attribute("href") or ""
                if "/maps/place/" in href and href not in seen:
                    seen.add(href)
                    hrefs.append(href)
                    if len(hrefs) >= max_results:
                        break
            except Exception:
                continue

        if len(hrefs) == prev_count:
            stale_scrolls += 1
        else:
            stale_scrolls = 0

        # Check for Google's end-of-results marker
        for end_sel in ("span.HlvSq", "p.fontBodyMedium > span"):
            end_el = await page.query_selector(end_sel)
            if end_el:
                try:
                    txt = await end_el.inner_text()
                    if is_end_of_results(txt):
                        logger.debug("Reached end of results.")
                        health.cards_found += len(hrefs)
                        return hrefs[:max_results]
                except Exception:
                    pass

        # Scroll the feed panel
        await feed_el.evaluate("el => el.scrollBy(0, el.clientHeight * 0.85)")
        await asyncio.sleep(random.uniform(SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX))

    # Final hard scroll to bottom in case lazy content still hasn't triggered
    try:
        await feed_el.evaluate("el => el.scrollTo(0, el.scrollHeight)")
        await asyncio.sleep(random.uniform(1.0, 2.0))
        cards = await page.query_selector_all(CARD_SELECTOR)
        for card in cards:
            try:
                href = await card.get_attribute("href") or ""
                if "/maps/place/" in href and href not in seen:
                    seen.add(href)
                    hrefs.append(href)
                    if len(hrefs) >= max_results:
                        break
            except Exception:
                continue
    except Exception:
        pass

    logger.debug(f"Collected {len(hrefs)} card hrefs.")
    health.cards_found += len(hrefs)
    return hrefs[:max_results]


async def _extract_place_data(
    page: Page,
    href: str,
    category: str,
    health: SelectorHealth,
) -> dict | None:
    """
    Navigate to a place detail page and extract all business fields.

    Returns a dict of raw data, or None if the name can't be found.
    Consent dialogs can re-appear on detail pages; handled here too.
    """
    try:
        await _navigate(page, href)
    except PlaywrightTimeout:
        logger.warning(f"Timed out loading place page: {href}")
        health.failures.append(f"detail-timeout:{href[:80]}")
        return None

    await _check_captcha(page)
    await _handle_consent(page)

    place_id = extract_place_id_from_url(page.url)

    name = await _get_text(page, NAME_SELECTORS)
    if not name:
        logger.warning(f"Could not extract business name from: {href}")
        health.failures.append(f"name-missing:{href[:80]}")
        return None
    health.names_extracted += 1

    address = await _get_text(page, ADDRESS_SELECTORS)
    if address:
        health.addresses_extracted += 1
    phone = await _get_text(page, PHONE_SELECTORS)
    if phone:
        health.phones_extracted += 1
    website_url = await _get_href(page, WEBSITE_SELECTORS)
    if website_url:
        health.websites_extracted += 1

    # Rating — try inner text, then aria-label
    rating: float | None = None
    rating_text = await _get_text(page, RATING_SELECTORS)
    if rating_text:
        rating = parse_rating(rating_text)
    if rating is None:
        for sel in RATING_SELECTORS:
            try:
                el = await page.query_selector(sel)
                if el:
                    aria = await el.get_attribute("aria-label") or ""
                    rating = parse_rating(aria)
                    if rating is not None:
                        break
            except Exception:
                continue
    if rating is not None:
        health.ratings_extracted += 1

    # Review count — prefer aria-label, fall back to inner text
    review_count: int | None = None
    for sel in REVIEW_SELECTORS:
        try:
            el = await page.query_selector(sel)
            if el:
                aria = await el.get_attribute("aria-label") or ""
                review_count = parse_review_count(aria)
                if review_count is None:
                    text = (await el.inner_text()).strip()
                    review_count = parse_review_count(text)
                if review_count is not None:
                    break
        except Exception:
            continue
    if review_count is not None:
        health.reviews_extracted += 1

    # --- New Phase 15 fields ---
    google_categories = await _get_all_texts(page, CATEGORY_SELECTORS, limit=4)
    if google_categories:
        health.categories_extracted += 1

    hours = await _get_text(page, HOURS_SELECTORS)
    if hours:
        health.hours_extracted += 1
        # Normalize to a single line (can be multi-line in the side panel)
        hours = " · ".join(line.strip() for line in hours.splitlines() if line.strip())

    description = await _get_text(page, DESCRIPTION_SELECTORS)
    if description:
        health.descriptions_extracted += 1

    photo_count: int | None = None
    photo_text = await _get_text(page, PHOTO_COUNT_SELECTORS)
    if photo_text:
        photo_count = parse_photo_count(photo_text)

    # Claim signal — presence of "Claim this business" ⇒ unclaimed listing
    is_claimed: bool | None = None
    for sel in CLAIM_SELECTORS:
        try:
            el = await page.query_selector(sel)
            if el:
                is_claimed = False
                break
        except Exception:
            continue
    if is_claimed is None and name:
        # No claim link found on a fully-loaded detail page ⇒ claimed.
        is_claimed = True

    return {
        "place_id": place_id,
        "name": name.strip(),
        "category": category,
        "address": address.strip() if address else None,
        "phone": phone.strip() if phone else None,
        "website_url": website_url,
        "rating": rating,
        "review_count": review_count,
        "google_categories": google_categories,
        "hours": hours,
        "business_description": description,
        "photo_count": photo_count,
        "is_claimed": is_claimed,
    }


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


async def is_duplicate(biz: dict, db: AsyncSession) -> bool:
    """
    Return True if the business already exists in the database.

    Checks place_id first (most reliable), then falls back to name + address.
    Exported so it can be tested independently.
    """
    place_id = biz.get("place_id")
    if place_id:
        result = await db.execute(select(Lead).where(Lead.place_id == place_id))
        if result.scalar_one_or_none():
            return True

    name = biz.get("name")
    address = biz.get("address")
    if name and address:
        result = await db.execute(select(Lead).where(Lead.name == name, Lead.address == address))
        if result.scalar_one_or_none():
            return True

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def scrape_category(
    category: str,
    db: AsyncSession,
    context: BrowserContext,
    health: SelectorHealth,
    max_results: int | None = None,
) -> list[dict]:
    """
    Scrape Google Maps for businesses in a given category.

    Args:
        category:    Search category string (e.g. "restaurants")
        db:          Async SQLAlchemy session for dedup checks
        context:     Shared Playwright BrowserContext (one per scrape run)
        health:      Shared SelectorHealth counter for this run
        max_results: Override; defaults to settings.scrape_max_results.

    Returns:
        A list of raw business dicts not already in the database.
    """
    cap = max_results if max_results is not None else settings.scrape_max_results
    search_url = build_search_url(category)
    logger.info(f"Starting scrape: '{category}' → {search_url}")

    page = await context.new_page()
    try:
        # Phase 1: collect card hrefs
        hrefs = await _collect_card_hrefs(page, search_url, cap, health)
        logger.info(f"[{category}] Collected {len(hrefs)} candidate listings.")

        if not hrefs:
            return []

        # Phase 2: visit each place page, extract data, dedup
        results: list[dict] = []
        for i, href in enumerate(hrefs, start=1):
            try:
                biz = await _extract_place_data(page, href, category, health)
                if biz is None:
                    continue

                if await is_duplicate(biz, db):
                    logger.debug(f"[{category}] Duplicate skipped: {biz['name']}")
                    continue

                results.append(biz)
                logger.debug(f"[{category}] {i}/{len(hrefs)} extracted: {biz['name']}")

                # Polite pause between place loads
                await asyncio.sleep(random.uniform(0.8, 2.0))

            except CaptchaEncountered:
                # CAPTCHA is a fatal, session-wide signal — bubble up.
                raise
            except Exception as e:
                logger.error(
                    f"[{category}] Error on listing {i}/{len(hrefs)}: {e}",
                    exc_info=True,
                )
                continue

        logger.info(f"[{category}] Done — {len(results)} new businesses found.")
        return results

    except CaptchaEncountered as e:
        health.captchas_encountered += 1
        logger.error(f"[{category}] {e}")
        raise
    except Exception as e:
        logger.error(f"[{category}] Fatal scrape error: {e}", exc_info=True)
        return []
    finally:
        await page.close()
