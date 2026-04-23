"""
Target business categories for the scraper and value multipliers used by
the lead scorer to bias the opportunity score toward high-payout industries.

CATEGORY_VALUE_MULTIPLIER reflects typical freelance web project payouts
in Boise. Dentists, HVAC, plumbers, chiropractors pay $3k-10k for a site;
restaurants typically pay $500-1500. Multiplier is applied to the 0-100
opportunity_score in src/scorer/lead.py.

New categories default to 1.0 if absent from the map.
"""

CATEGORIES: list[str] = [
    "restaurants",
    "auto repair",
    "hair salon",
    "plumbers",
    "electricians",
    "HVAC",
    "landscaping",
    "cleaning services",
    "contractors",
    "dentist",
    "chiropractor",
    "pet grooming",
    "local retail",
]

# Higher = more payout potential per lead.
CATEGORY_VALUE_MULTIPLIER: dict[str, float] = {
    "dentist": 1.5,
    "chiropractor": 1.4,
    "HVAC": 1.4,
    "plumbers": 1.4,
    "electricians": 1.3,
    "contractors": 1.3,
    "auto repair": 1.15,
    "landscaping": 1.1,
    "cleaning services": 1.0,
    "hair salon": 1.0,
    "pet grooming": 0.95,
    "local retail": 0.95,
    "restaurants": 0.85,
}


def category_multiplier(category: str | None) -> float:
    """Return the value multiplier for a category, or 1.0 if unknown/None."""
    if not category:
        return 1.0
    return CATEGORY_VALUE_MULTIPLIER.get(category, 1.0)
