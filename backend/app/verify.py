from __future__ import annotations
from app.data_loader import load_brand_rules
from app.evidence import is_health_claim


class VerificationResult:
    """Carries pass/fail plus a specific, human-readable reason for each
    failure. The reason strings are what feed back into retry_feedback
    in B7's repair loop — vague reasons produce vague repairs, so these
    need to be precise enough for the model to actually act on."""
    def __init__(self, passed: bool, failed_checks: list[str]):
        self.passed = passed
        self.failed_checks = failed_checks


def check_structure(raw_output: dict) -> VerificationResult:
    """Checks the response even parses into the shape we expect.
    Runs first — if this fails, nothing else downstream can run safely,
    since later checks assume headline/subline/claims exist as strings/list."""
    failures = []

    if not isinstance(raw_output, dict):
        return VerificationResult(False, ["Response is not a JSON object"])

    if not isinstance(raw_output.get("headline"), str) or not raw_output.get("headline", "").strip():
        failures.append("Missing or empty 'headline' field")

    if not isinstance(raw_output.get("subline"), str) or not raw_output.get("subline", "").strip():
        failures.append("Missing or empty 'subline' field")

    claims = raw_output.get("claims")
    if not isinstance(claims, list):
        failures.append("'claims' field is missing or not a list")
    else:
        for i, c in enumerate(claims):
            if not isinstance(c, dict):
                failures.append(f"claims[{i}] is not an object")
                continue
            if not c.get("text"):
                failures.append(f"claims[{i}] missing 'text'")
            if c.get("source_type") not in ("attribute", "review"):
                failures.append(f"claims[{i}] has invalid source_type: {c.get('source_type')!r}")
            if not c.get("source_id"):
                failures.append(f"claims[{i}] missing 'source_id'")

    return VerificationResult(passed=len(failures) == 0, failed_checks=failures)


def check_length(raw_output: dict) -> VerificationResult:
    rules = load_brand_rules()
    failures = []

    headline = raw_output.get("headline", "")
    subline = raw_output.get("subline", "")

    if len(headline) > rules["max_headline_chars"]:
        failures.append(
            f"Headline is {len(headline)} chars, exceeds max of {rules['max_headline_chars']}"
        )
    if len(subline) > rules["max_subline_chars"]:
        failures.append(
            f"Subline is {len(subline)} chars, exceeds max of {rules['max_subline_chars']}"
        )

    return VerificationResult(passed=len(failures) == 0, failed_checks=failures)


def check_banned_words(raw_output: dict) -> VerificationResult:
    """Checks headline + subline text only — NOT the claims' source data,
    since a banned word appearing inside a review or the product's own
    name is the merchant's problem, not ours (per the README's own rule).
    We only care whether WE wrote a banned word into the copy."""
    rules = load_brand_rules()
    failures = []

    combined_text = f"{raw_output.get('headline', '')} {raw_output.get('subline', '')}".lower()

    for banned in rules["banned_words"]:
        if banned.lower() in combined_text:
            failures.append(f"Copy contains banned word/phrase: '{banned}'")

    return VerificationResult(passed=len(failures) == 0, failed_checks=failures)


def check_citation_coverage(raw_output: dict) -> VerificationResult:
    """Catches exactly the 'immune support' bug we found in B3 testing:
    every specific factual word/phrase in the headline+subline should be
    traceable to *something* in the claims list. This is intentionally
    a rough heuristic, not a precise NLP check — it flags claim TEXT that
    doesn't loosely appear anywhere in the actual headline/subline, which
    catches the opposite problem (a claim listed but never actually used
    in the copy) and is a good sanity check, but does NOT catch a fact
    written into the copy with zero matching claim at all as reliably as
    we'd like. That harder case ('unclaimed but real-sounding facts in
    the copy') is exactly what B5's groundedness LLM-judge is for —
    this check is a cheap first pass, not the final word."""
    failures = []
    claims = raw_output.get("claims", [])

    if not isinstance(claims, list) or len(claims) == 0:
        # Note: NOT necessarily a failure — a product with no attributes
        # and no reviews (per prompt rule 4) is allowed to produce
        # generic, claim-free copy. We only flag zero claims as
        # suspicious, not automatically wrong; B5 or a human reviewer
        # makes the final call using has_no_reviews/has_no_attributes.
        return VerificationResult(passed=True, failed_checks=[])

    headline_lower = raw_output.get("headline", "").lower()
    subline_lower = raw_output.get("subline", "").lower()
    combined = f"{headline_lower} {subline_lower}"

    for c in claims:
        claim_text = str(c.get("text", "")).lower().strip()
        if claim_text and claim_text not in combined:
            failures.append(
                f"Claim '{c.get('text')}' is listed but its exact wording "
                f"doesn't appear in the headline/subline — check for drift"
            )

    return VerificationResult(passed=len(failures) == 0, failed_checks=failures)


def check_no_direct_health_language(raw_output: dict) -> VerificationResult:
    """Separate from check_banned_words — this is the compliance-policy
    check ('no health or medical claims, even if a review makes one'),
    reusing the same keyword screen from B1 but applied to the COPY
    itself this time, not the source reviews. This is what would have
    caught 'immune support' in the B3 test run, since 'immune' and
    'support' language around health trips a broader net than the
    literal banned_words list (which only has 'cure', 'miracle', etc.,
    not 'immune support')."""
    failures = []
    combined = f"{raw_output.get('headline', '')} {raw_output.get('subline', '')}"

    if is_health_claim(combined):
        failures.append(
            "Copy contains health/medical-adjacent language "
            "(claims policy bans this even if it wasn't in banned_words)"
        )

    # extra net for the specific case we found: "immune support" /
    # "supports immune" type phrasing that the base keyword list misses
    lowered = combined.lower()
    if "immune" in lowered or "immunity" in lowered:
        failures.append(
            "Copy references immune system / immunity — treated as an "
            "implied health claim regardless of source"
        )

    return VerificationResult(passed=len(failures) == 0, failed_checks=failures)

def run_structural_checks(raw_output: dict) -> VerificationResult:
    """Entry point B7 calls for the HARD gate. Citation-coverage text
    matching is deliberately excluded from this hard gate — as proven
    in testing, it false-positives on normal paraphrasing (e.g. '60' vs
    'sixty', 'great taste' vs 'taste great'). It's still useful as a
    signal, just not a fair pass/fail bar on its own. See
    check_citation_coverage_advisory below — B7 can log it without
    rejecting on it."""
    structure = check_structure(raw_output)
    if not structure.passed:
        return structure

    all_failures = []
    for check_fn in [
        check_length,
        check_banned_words,
        check_no_direct_health_language,
    ]:
        result = check_fn(raw_output)
        all_failures.extend(result.failed_checks)

    return VerificationResult(passed=len(all_failures) == 0, failed_checks=all_failures)


def check_citation_coverage_advisory(raw_output: dict) -> VerificationResult:
    """Same logic as before, kept as a separate advisory-only function.
    B7 logs this in attempt_log for transparency but does NOT reject
    generations based on it alone — real groundedness is decided by
    run_groundedness_check below instead."""
    return check_citation_coverage(raw_output)