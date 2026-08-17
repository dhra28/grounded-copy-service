from __future__ import annotations
import re

# Words that assert supremacy/absoluteness without being independently
# verifiable from attributes or reviews — distinct from banned_words,
# which are explicit merchant-specified terms. This list is a heuristic,
# not exhaustive; flagging that honestly rather than pretending it's complete.
SUPERLATIVE_PATTERNS = [
    r"\bultimate\b", r"\bunbeatable\b", r"\bunmatched\b", r"\bperfect\b",
    r"\bflawless\b", r"\bsuperior\b", r"\bunrivaled\b", r"\bworld[- ]class\b",
    r"\btop[- ]rated\b", r"\bnumber one\b", r"\bindustry[- ]leading\b",
]

SUPERLATIVE_REGEX = re.compile("|".join(SUPERLATIVE_PATTERNS), re.IGNORECASE)


class ComplianceResult:
    def __init__(self, passed: bool, issues: list[str]):
        self.passed = passed
        self.issues = issues


def check_unverifiable_superlatives(raw_output: dict) -> ComplianceResult:
    """A superlative claim would need its OWN evidence to be legitimate
    (e.g. an attribute or review that literally supports 'top-rated').
    We don't try to check whether such evidence exists — that's a
    judgment call better suited to B5's groundedness judge. This check
    is a cheap, deterministic tripwire: if a superlative appears at all,
    flag it for a human/reviewer to look at, since the brand rules ban
    UNVERIFIABLE ones specifically and code alone can't confirm which
    kind this is."""
    combined = f"{raw_output.get('headline', '')} {raw_output.get('subline', '')}"
    matches = SUPERLATIVE_REGEX.findall(combined)

    if matches:
        return ComplianceResult(
            passed=False,
            issues=[f"Contains unverifiable superlative language: {matches}"],
        )
    return ComplianceResult(passed=True, issues=[])


def run_compliance_checks(raw_output: dict) -> ComplianceResult:
    """Single entry point B7 will call, alongside run_structural_checks
    and run_groundedness_check. Currently just wraps the superlative
    check, but kept as its own function/module (rather than folded into
    verify.py) since 'compliance with brand policy' and 'structural
    correctness' are conceptually different concerns the brief calls
    out separately — worth keeping that separation visible in the code,
    not just in prose."""
    return check_unverifiable_superlatives(raw_output)