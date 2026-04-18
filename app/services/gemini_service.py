"""
app/services/gemini_service.py
------------------------------
All LLM interaction logic lives here. Routes stay completely free of SDK code.

Responsibilities:
  - Configure the Gemini SDK once at module load (singleton pattern).
  - Expose one public async-compatible function per endpoint.
  - Apply GenerationConfig per call, using response_mime_type="application/json"
    where JSON output is required (analyze_complexity).
  - Sanitize model output through utility functions that strip Markdown fences,
    collapse stray whitespace, and safely parse JSON.
  - Raise descriptive HTTPExceptions so routes never need to catch SDK errors.
"""

import json
import logging
import re
from typing import Any

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from fastapi import HTTPException

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SDK Initialization — runs once when the module is first imported.
# ---------------------------------------------------------------------------
_settings = get_settings()
genai.configure(api_key=_settings.GEMINI_API_KEY)


# ---------------------------------------------------------------------------
# Internal — Sanitization Utilities
# ---------------------------------------------------------------------------

def _strip_markdown_fences(text: str) -> str:
    """
    Remove any Markdown code fences that an LLM may emit despite instructions.

    Handles patterns like:
        ```python\\n...\\n```
        ```json\\n...\\n```
        ```\\n...\\n```

    Args:
        text: Raw string from the model.

    Returns:
        Cleaned string with fences removed and leading/trailing whitespace stripped.
    """
    # Match an optional language tag on the opening fence, e.g. ```python
    cleaned = re.sub(
        r"^```[a-zA-Z0-9_+-]*\n?",  # opening fence
        "",
        text.strip(),
    )
    cleaned = re.sub(r"\n?```$", "", cleaned.strip())  # closing fence
    return cleaned.strip()


def _parse_json_safely(raw: str, required_keys: list[str]) -> dict[str, Any]:
    """
    Parse a JSON string returned by the model and validate that all
    *required_keys* are present.

    Applies `_strip_markdown_fences` first as a defensive measure, because
    even with `response_mime_type="application/json"` some model versions
    occasionally wrap output in fences.

    Args:
        raw: Raw model response string.
        required_keys: Keys that must exist in the parsed dict.

    Returns:
        Parsed dictionary.

    Raises:
        HTTPException(500): On JSON parse failure or missing keys.
    """
    cleaned = _strip_markdown_fences(raw)

    try:
        data: dict = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error(
            "JSON parse failed. Error: %s | Raw (first 300 chars): %.300s",
            exc,
            raw,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                f"The model returned malformed JSON that could not be parsed. "
                f"Parser error: {exc}. "
                f"Raw response preview: {raw[:200]}"
            ),
        ) from exc

    missing = [k for k in required_keys if k not in data]
    if missing:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Model JSON response is missing required keys: {missing}. "
                f"Raw response preview: {raw[:200]}"
            ),
        )

    return data


# ---------------------------------------------------------------------------
# Internal — Core LLM caller
# ---------------------------------------------------------------------------

def _call_gemini(
    system_prompt: str,
    user_message: str,
    *,
    generation_config: GenerationConfig | None = None,
) -> str:
    """
    Construct a full prompt from *system_prompt* + *user_message*, invoke
    the Gemini model, and return the raw text response.

    Args:
        system_prompt: The instruction prompt loaded from the .env variable.
        user_message: The user-supplied payload formatted as a string.
        generation_config: Optional Gemini GenerationConfig (e.g. for JSON mode).

    Returns:
        Raw response text from the model.

    Raises:
        HTTPException(400): Model refused the content (safety filter triggered).
        HTTPException(503): Gemini API is unreachable or returned an error.
    """
    model = genai.GenerativeModel(
        model_name=_settings.GEMINI_MODEL,
        system_instruction=system_prompt,
        generation_config=generation_config,
    )

    try:
        response = model.generate_content(user_message)

        # Detect safety / content filter blocks
        if not response.parts:
            finish_reason = "UNKNOWN"
            if response.candidates:
                finish_reason = str(response.candidates[0].finish_reason)
            raise HTTPException(
                status_code=400,
                detail=(
                    "The model refused to generate a response. "
                    f"Finish reason: {finish_reason}. "
                    "Your input may have triggered a safety filter — "
                    "try rephrasing your request."
                ),
            )

        return response.text

    except HTTPException:
        raise  # Re-raise structured errors as-is
    except Exception as exc:
        logger.exception("Gemini API call failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Gemini API error: {type(exc).__name__}: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Public Service Functions — one per route
# ---------------------------------------------------------------------------

def generate_code(idea: str, language: str) -> dict[str, str]:
    """
    Convert a natural-language *idea* into working code in *language*.

    Args:
        idea: Natural-language description of what to build.
        language: Target programming language.

    Returns:
        dict with keys `code` and `language`.
    """
    user_message = (
        f"Target language: {language}\n\n"
        f"Idea: {idea}"
    )
    raw = _call_gemini(_settings.PROMPT_GENERATE_CODE, user_message)
    return {
        "code": _strip_markdown_fences(raw),
        "language": language,
    }


def explain_code(code: str) -> dict[str, str]:
    """
    Produce a Markdown, line-by-line explanation of *code*.

    Args:
        code: Source code to explain.

    Returns:
        dict with key `explanation_md`.
    """
    raw = _call_gemini(
        _settings.PROMPT_EXPLAIN_CODE,
        f"Code to explain:\n{code}",
    )
    return {"explanation_md": raw.strip()}


def analyze_complexity(code: str) -> dict[str, str]:
    """
    Estimate Time & Space complexity and identify bottlenecks.

    Uses `response_mime_type="application/json"` in the GenerationConfig
    to force the Gemini API to return valid JSON at the transport level.

    Args:
        code: Source code to analyse.

    Returns:
        dict with keys: time_complexity, space_complexity, bottlenecks, analysis_md.
    """
    config = GenerationConfig(response_mime_type="application/json")
    raw = _call_gemini(
        _settings.PROMPT_ANALYZE_COMPLEXITY,
        f"Code to analyse:\n{code}",
        generation_config=config,
    )
    return _parse_json_safely(
        raw,
        required_keys=["time_complexity", "space_complexity", "bottlenecks", "analysis_md"],
    )


def rubber_duck(code_context: str, question: str) -> dict[str, str]:
    """
    Answer a debugging *question* in the context of *code_context*.

    Args:
        code_context: The code block that provides context.
        question: The user's debugging or conceptual question.

    Returns:
        dict with key `answer_md`.
    """
    user_message = (
        f"Code context:\n{code_context}\n\n"
        f"Question: {question}"
    )
    raw = _call_gemini(_settings.PROMPT_RUBBER_DUCK, user_message)
    return {"answer_md": raw.strip()}


def convert_language(code: str, target_language: str) -> dict[str, str]:
    """
    Translate *code* into *target_language* using idiomatic patterns.

    Args:
        code: Source code to translate.
        target_language: Target programming language.

    Returns:
        dict with keys `converted_code` and `target_language`.
    """
    user_message = (
        f"Target language: {target_language}\n\n"
        f"Code to translate:\n{code}"
    )
    raw = _call_gemini(_settings.PROMPT_CONVERT_LANGUAGE, user_message)
    return {
        "converted_code": _strip_markdown_fences(raw),
        "target_language": target_language,
    }


def generate_docstring(code: str) -> dict[str, str]:
    """
    Generate a professional docstring and return both the standalone
    docstring and the full code with the docstring injected.

    Strategy: The model is instructed to return the *full code with the
    docstring inserted*. We then extract the docstring from it rather than
    asking for two separate outputs (more reliable with a single LLM call).

    Args:
        code: The function or class that needs a docstring.

    Returns:
        dict with keys `docstring` and `code_with_docstring`.
    """
    raw = _call_gemini(
        _settings.PROMPT_GENERATE_DOCSTRING,
        f"Code:\n{code}",
    )

    code_with_docstring = _strip_markdown_fences(raw)

    # Attempt to extract just the docstring from the returned code.
    # Works for Python triple-quote docstrings; for other languages we
    # fall back to the full response as the docstring.
    docstring = _extract_docstring(code_with_docstring)

    return {
        "docstring": docstring,
        "code_with_docstring": code_with_docstring,
    }


def _extract_docstring(code: str) -> str:
    """
    Attempt to extract the first docstring (triple-quoted) from *code*.

    Falls back to the full code string if no docstring pattern is found,
    which handles non-Python languages gracefully.

    Args:
        code: Source code that should contain a docstring.

    Returns:
        Extracted docstring string, or the full code as a fallback.
    """
    # Match Python triple-quote docstrings (both ''' and \""")
    match = re.search(r'(\"\"\"[\s\S]*?\"\"\"|\'\'\'[\s\S]*?\'\'\')', code)
    if match:
        return match.group(0).strip('"\' \n')
    return code  # Fallback: return full code
