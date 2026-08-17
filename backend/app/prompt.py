import json
from app.data_loader import load_brand_rules
from app.evidence import get_evidence_for


def build_system_prompt() -> str:
    rules = load_brand_rules()

    return f"""You write short product copy (a headline and a subline) for an ecommerce store.

TONE: {rules['tone']}

HARD LIMITS:
- Headline: max {rules['max_headline_chars']} characters
- Subline: max {rules['max_subline_chars']} characters
- Banned words (never use, in any form): {", ".join(rules['banned_words'])}
- {rules['required']}

CLAIMS POLICY (read carefully, this is the most important part):
{rules['claims_policy']}

You will be given:
- The product's attributes (specs, from the merchant's own data)
- A list of customer reviews that have ALREADY been screened for you —
  unusable claims (health/medical claims, claims that violate policy)
  have been removed before you saw them. Treat every review you're
  given as fair game to reference, but you still must not exaggerate
  or add anything the review didn't actually say.
- Flags telling you if reviews conflict with each other, or if there
  are no reviews / no attributes at all for this product.

RULES FOR HANDLING EVIDENCE:
1. Every factual claim in your copy (not tone/style words) MUST be
   backed by either a product attribute or a review, and you must
   cite exactly which one in the "claims" field.
2. If "has_conflicting_reviews" is true, do NOT assert either side of
   the disagreement as fact. Either omit the disputed point entirely,
   or stick to what the product attributes confirm instead.
3. If there are no reviews at all, write copy grounded only in the
   attributes. Do not invent a "customers love it" type claim with
   no review to support it.
4. If there are no attributes and no usable reviews, write short,
   honest, tone-appropriate copy using only the product name and
   category — do not invent any specific facts. It is fine for the
   copy to be more generic in this case; that's expected, not a failure.
5. Never restate a banned word even if it appears in the product's own
   name — the banned-word rule applies to the copy you write, not to
   the source data.

Respond with a single JSON object matching the required schema. No other text."""


def build_user_prompt(product_id: str) -> tuple[str, dict]:
    """Returns (prompt_text, evidence) — we return evidence too because
    the verifier in B4/B5 needs the exact same filtered evidence set to
    check citations against, and we don't want it re-deriving it separately
    and risking drift between what the model saw and what we verify against."""
    evidence = get_evidence_for(product_id)
    product = evidence["product"]

    reviews_block = [
        {"review_id": r["review_id"], "text": r["text"], "rating": r["rating"]}
        for r in evidence["usable_reviews"]
    ]

    payload = {
        "product_id": product["product_id"],
        "name": product["name"],
        "category": product["category"],
        "price": product["price"],
        "attributes": product.get("attributes", {}),
        "usable_reviews": reviews_block,
        "has_conflicting_reviews": evidence["has_conflicting_reviews"],
        "has_no_reviews": evidence["has_no_reviews"],
        "has_no_attributes": evidence["has_no_attributes"],
    }

    prompt_text = (
        "Write a headline and subline for this product, following the "
        "system rules exactly.\n\n"
        f"{json.dumps(payload, indent=2)}"
    )

    return prompt_text, evidence


# Structured-output schema for Gemini's response_schema.
# Matches LLMCopyOutput in schemas.py.
COPY_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "subline": {"type": "string"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "source_type": {"type": "string", "enum": ["attribute", "review"]},
                    "source_id": {"type": "string"},
                },
                "required": ["text", "source_type", "source_id"],
            },
        },
    },
    "required": ["headline", "subline", "claims"],
}