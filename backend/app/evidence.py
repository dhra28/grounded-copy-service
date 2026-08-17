import re
from app.data_loader import get_product, get_reviews_for


# Keyword screen for health/medical claims. This is a blunt instrument —
# a fixed keyword list will always miss paraphrases and occasionally
# over-flag something harmless. That's an honest limitation, not a bug,
# and it's exactly what we'll call out in the README's eval-limitations
# section. For 18 products and a 12h budget, a keyword list beats trying
# to build a real medical-claim classifier.
HEALTH_KEYWORDS = [
    "cure", "cured", "curing",
    "insomnia", "disease", "diagnos",
    "immune system", "boost immunity",
    "heal", "healed", "healing",
    "treat", "treats", "treated", "treatment",
    "prevent", "prevents", "prevented",
    "symptom", "symptoms",
    "pain gone", "pain-free", "arthritis",
    "medical", "prescription",
]

HEALTH_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in HEALTH_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def is_health_claim(text: str) -> bool:
    return bool(HEALTH_PATTERN.search(text))


def filter_reviews(product_id: str) -> dict:
    """Splits a product's reviews into what's safe to hand the LLM
    and what got excluded, with a reason for each — the reason string
    goes straight into attempt_log later, so a reviewer can see exactly
    why R913 ('fixed my insomnia') never reached the prompt for P115."""
    reviews = get_reviews_for(product_id)

    usable = []
    excluded = []

    for r in reviews:
        if is_health_claim(r["text"]):
            excluded.append({
                "review_id": r["review_id"],
                "reason": "health_or_medical_claim",
                "text": r["text"],
            })
        else:
            usable.append(r)

    return {
        "usable_reviews": usable,
        "excluded_reviews": excluded,
    }


def detect_rating_conflict(reviews: list[dict]) -> bool:
    """Rough proxy for 'these reviews disagree with each other'.
    We don't try to semantically compare review text (that's a much
    harder problem and arguably needs an LLM call itself, which we're
    not spending budget on here). Rating spread is a cheap, honest
    stand-in: a 1-star and a 5-star on the same product is a strong
    signal something is contested, even without reading the text."""
    if len(reviews) < 2:
        return False
    ratings = [r["rating"] for r in reviews]
    return (max(ratings) - min(ratings)) >= 3


def get_evidence_for(product_id: str) -> dict:
    """Single entry point Phase B2's prompt builder will call.
    Bundles attributes + filtered reviews + conflict flag + missing-data
    flags into one object, so the prompt-building code doesn't need to
    know anything about health keywords or rating math."""
    product = get_product(product_id)
    if product is None:
        raise ValueError(f"Unknown product_id: {product_id}")

    filtered = filter_reviews(product_id)
    usable = filtered["usable_reviews"]

    return {
        "product": product,
        "usable_reviews": usable,
        "excluded_reviews": filtered["excluded_reviews"],
        "has_conflicting_reviews": detect_rating_conflict(usable),
        "has_no_reviews": len(usable) == 0,
        "has_no_attributes": len(product.get("attributes", {})) == 0,
    }