"""A small, hand-crafted set of adversarial test cases — NOT loaded by
the real app, only used by test_synthetic.py. Kept separate from
data/products.json and data/reviews.json so the real starter data stays
untouched and these are clearly marked as synthetic, not submitted as
real eval results."""

SYNTHETIC_PRODUCTS = [
    {
        "product_id": "SYN001",
        "name": "Wrong-Product Review Test Mug",
        "category": "Home",
        "price": 14.0,
        "attributes": {"material": "ceramic", "capacity_ml": 350},
        "current_headline": None,
    },
    {
        "product_id": "SYN002",
        "name": "Foreign Language Review Test Candle",
        "category": "Home",
        "price": 20.0,
        "attributes": {"scent": "vanilla", "burn_hours": 40},
        "current_headline": None,
    },
    {
        "product_id": "SYN003",
        "name": "Spec-Contradicting Review Test Charger",
        "category": "Electronics",
        "price": 25.0,
        "attributes": {"output_watts": 20, "ports": 1},
        "current_headline": None,
    },
]

SYNTHETIC_REVIEWS = [
    # Review actually about a DIFFERENT product entirely — tests whether
    # our pipeline blindly trusts anything tagged with the right product_id
    {
        "review_id": "SYNR001",
        "product_id": "SYN001",
        "rating": 5,
        "verified_purchase": True,
        "text": "This laptop bag has held up great for a year of daily commuting.",
    },
    # Non-English review — tests whether the health-keyword filter and
    # the LLM judge behave sensibly on text they can't screen normally
    {
        "review_id": "SYNR002",
        "product_id": "SYN002",
        "rating": 4,
        "verified_purchase": True,
        "text": "Muy buena fragancia, dura toda la tarde en mi sala.",
    },
    # Review that directly contradicts the hard spec number — tests
    # whether the model favors the verified attribute over a review claim
    {
        "review_id": "SYNR003",
        "product_id": "SYN003",
        "rating": 3,
        "verified_purchase": True,
        "text": "Charges at 65 watts, way faster than my old charger.",
    },
]