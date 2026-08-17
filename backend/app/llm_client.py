from __future__ import annotations
import re
import time
import json
import google.generativeai as genai
from google.api_core.exceptions import DeadlineExceeded, GoogleAPICallError, ResourceExhausted

from app.config import settings
from app.prompt import build_system_prompt, build_user_prompt, COPY_RESPONSE_SCHEMA

genai.configure(api_key=settings.gemini_api_key)


class LLMCallResult:
    def __init__(self, success: bool, raw_output: dict | None,
                 error: str | None, latency_ms: int,
                 input_tokens: int, output_tokens: int):
        self.success = success
        self.raw_output = raw_output
        self.error = error
        self.latency_ms = latency_ms
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


def _extract_retry_delay(error_message: str) -> float:
    """Gemini's 429 error text includes a suggested wait time, e.g.
    'Please retry in 35.054407733s.' — parse that out so we wait exactly
    as long as needed, not an arbitrary guess. Falls back to a safe
    default of 20s if the message format ever changes and parsing fails,
    rather than crashing on a regex miss."""
    match = re.search(r"retry in ([\d.]+)s", error_message)
    if match:
        return float(match.group(1)) + 1  # +1s buffer for safety
    return 20.0


def call_llm(product_id: str, retry_feedback: str | None = None) -> tuple[LLMCallResult, dict]:
    """Same contract as before. Now distinguishes ResourceExhausted (429,
    rate limit) from other transient errors: a 429 gets a targeted wait-
    and-retry using the delay Gemini itself suggests, since that's a
    near-guaranteed recovery rather than a coin flip like a generic
    timeout or connection error would be."""
    user_prompt, evidence = build_user_prompt(product_id)

    if retry_feedback:
        user_prompt += (
            f"\n\nYour previous attempt was rejected for this reason:\n"
            f"{retry_feedback}\n"
            f"Fix this specific issue and resubmit."
        )

    model = genai.GenerativeModel(
        model_name=settings.llm_model.strip(),
        system_instruction=build_system_prompt(),
        generation_config=genai.GenerationConfig(
            max_output_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            response_mime_type="application/json",
            response_schema=COPY_RESPONSE_SCHEMA,
        ),
    )

    start = time.monotonic()
    last_error = None

    for attempt in range(2):
        try:
            response = model.generate_content(
                user_prompt,
                request_options={"timeout": settings.llm_timeout_seconds},
            )
            latency_ms = int((time.monotonic() - start) * 1000)

            try:
                parsed = json.loads(response.text)
            except (json.JSONDecodeError, ValueError):
                return LLMCallResult(
                    success=False, raw_output=None,
                    error="Model response was not valid JSON",
                    latency_ms=latency_ms,
                    input_tokens=response.usage_metadata.prompt_token_count,
                    output_tokens=response.usage_metadata.candidates_token_count,
                ), evidence

            return LLMCallResult(
                success=True,
                raw_output=parsed,
                error=None,
                latency_ms=latency_ms,
                input_tokens=response.usage_metadata.prompt_token_count,
                output_tokens=response.usage_metadata.candidates_token_count,
            ), evidence

        except ResourceExhausted as e:
            # 429 — rate limited. Wait the SUGGESTED time, then let the
            # loop retry once. This is the one error type where retrying
            # immediately would just fail again, so we wait deliberately
            # instead of wasting the attempt.
            wait_s = _extract_retry_delay(str(e))
            last_error = f"Rate limited (429), waited {wait_s:.1f}s: {e}"
            if attempt == 0:  # only wait if we're going to try again
                time.sleep(wait_s)
        except DeadlineExceeded:
            last_error = f"LLM request timed out after {settings.llm_timeout_seconds}s"
        except GoogleAPICallError as e:
            last_error = f"LLM API error: {e}"

    latency_ms = int((time.monotonic() - start) * 1000)
    return LLMCallResult(
        success=False, raw_output=None, error=last_error,
        latency_ms=latency_ms, input_tokens=0, output_tokens=0,
    ), evidence