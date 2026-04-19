"""
app/services/gemini_service.py
------------------------------
All LLM interaction logic with API key rotation.
"""

import json
import logging
import re
from typing import Any, List, Optional

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from fastapi import HTTPException

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

# ---------------------------------------------------------------------------
# API Key Rotation State
# ---------------------------------------------------------------------------
class APIKeyRotator:
    """Manage multiple API keys with quota exhaustion fallback."""
    
    def __init__(self, keys: List[str]):
        self._keys = keys
        self._current_index = 0
        self._exhausted_keys: set = set()
    
    @property
    def current_key(self) -> str:
        return self._keys[self._current_index]
    
    def mark_current_exhausted(self):
        """Mark current key as quota-exhausted and move to next."""
        self._exhausted_keys.add(self.current_key)
        logger.warning(f"API key exhausted: {self.current_key[:8]}...")
        
        if len(self._exhausted_keys) >= len(self._keys):
            raise HTTPException(
                status_code=429,
                detail="All API keys have exhausted their quotas. Please try again later."
            )
        
        self._current_index = (self._current_index + 1) % len(self._keys)
        # Skip already exhausted keys
        while self.current_key in self._exhausted_keys:
            self._current_index = (self._current_index + 1) % len(self._keys)
        
        logger.info(f"Switched to API key: {self.current_key[:8]}...")
    
    def reset_for_retry(self):
        """Reset exhausted set - useful for transient errors."""
        self._exhausted_keys.clear()
        self._current_index = 0


# Initialize the rotator
_key_rotator = APIKeyRotator(_settings.GEMINI_API_KEYS_LIST)


def _is_quota_exhausted(error: Exception) -> bool:
    """Check if error indicates quota exhaustion."""
    error_str = str(error).lower()
    return (
        "429" in error_str or
        "quota" in error_str or
        "resource exhausted" in error_str or
        "rate limit" in error_str
    )


# ---------------------------------------------------------------------------
# Internal — Sanitization Utilities (UNCHANGED)
# ---------------------------------------------------------------------------
def _strip_markdown_fences(text: str) -> str:
    cleaned = re.sub(r"^```[a-zA-Z0-9_+-]*\n?", "", text.strip())
    cleaned = re.sub(r"\n?```$", "", cleaned.strip())
    return cleaned.strip()


def _parse_json_safely(raw: str, required_keys: list[str]) -> dict[str, Any]:
    cleaned = _strip_markdown_fences(raw)
    try:
        data: dict = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse failed. Error: %s | Raw: %.300s", exc, raw)
        raise HTTPException(
            status_code=500,
            detail=f"Model returned malformed JSON. Error: {exc}"
        ) from exc
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"JSON missing required keys: {missing}"
        )
    return data


# ---------------------------------------------------------------------------
# Internal — Core LLM caller WITH KEY ROTATION
# ---------------------------------------------------------------------------
def _call_gemini_with_rotation(
    system_prompt: str,
    user_message: str,
    *,
    generation_config: Optional[GenerationConfig] = None,
    max_retries: int = 3,
) -> str:
    """
    Call Gemini with automatic key rotation on quota exhaustion.
    Tries each available key up to max_retries times.
    """
    last_error = None
    
    for attempt in range(max_retries):
        current_key = _key_rotator.current_key
        
        try:
            # Configure with current key
            genai.configure(api_key=current_key)
            
            model = genai.GenerativeModel(
                model_name=_settings.GEMINI_MODEL,
                system_instruction=system_prompt,
                generation_config=generation_config,
            )
            
            response = model.generate_content(user_message)
            
            if not response.parts:
                finish_reason = "UNKNOWN"
                if response.candidates:
                    finish_reason = str(response.candidates[0].finish_reason)
                raise HTTPException(
                    status_code=400,
                    detail=f"Model refused response. Finish reason: {finish_reason}"
                )
            
            return response.text
            
        except Exception as exc:
            last_error = exc
            logger.warning(f"Attempt {attempt + 1} failed with key {current_key[:8]}...: {type(exc).__name__}")
            
            if _is_quota_exhausted(exc):
                _key_rotator.mark_current_exhausted()
                continue  # Try next key
            else:
                # Non-quota error - don't rotate, just raise
                break
    
    # All retries exhausted
    if isinstance(last_error, HTTPException):
        raise last_error
    
    logger.exception("All API call attempts failed")
    raise HTTPException(
        status_code=503,
        detail=f"Gemini API error after {max_retries} attempts: {type(last_error).__name__}: {last_error}"
    ) from last_error


# ---------------------------------------------------------------------------
# Public Service Functions (ONLY CHANGE: _call_gemini → _call_gemini_with_rotation)
# ---------------------------------------------------------------------------
def generate_code(idea: str, language: str) -> dict[str, str]:
    user_message = f"Target language: {language}\n\nIdea: {idea}"
    raw = _call_gemini_with_rotation(_settings.PROMPT_GENERATE_CODE, user_message)
    return {"code": _strip_markdown_fences(raw), "language": language}


def explain_code(code: str) -> dict[str, str]:
    raw = _call_gemini_with_rotation(_settings.PROMPT_EXPLAIN_CODE, f"Code to explain:\n{code}")
    return {"explanation_md": raw.strip()}


def analyze_complexity(code: str) -> dict[str, str]:
    config = GenerationConfig(response_mime_type="application/json")
    raw = _call_gemini_with_rotation(
        _settings.PROMPT_ANALYZE_COMPLEXITY,
        f"Code to analyse:\n{code}",
        generation_config=config,
    )
    return _parse_json_safely(
        raw,
        required_keys=["time_complexity", "space_complexity", "bottlenecks", "analysis_md"],
    )


def rubber_duck(code_context: str, question: str) -> dict[str, str]:
    user_message = f"Code context:\n{code_context}\n\nQuestion: {question}"
    raw = _call_gemini_with_rotation(_settings.PROMPT_RUBBER_DUCK, user_message)
    return {"answer_md": raw.strip()}


def convert_language(code: str, target_language: str) -> dict[str, str]:
    user_message = f"Target language: {target_language}\n\nCode to translate:\n{code}"
    raw = _call_gemini_with_rotation(_settings.PROMPT_CONVERT_LANGUAGE, user_message)
    return {"converted_code": _strip_markdown_fences(raw), "target_language": target_language}


def generate_docstring(code: str) -> dict[str, str]:
    raw = _call_gemini_with_rotation(_settings.PROMPT_GENERATE_DOCSTRING, f"Code:\n{code}")
    code_with_docstring = _strip_markdown_fences(raw)
    docstring = _extract_docstring(code_with_docstring)
    return {"docstring": docstring, "code_with_docstring": code_with_docstring}


def _extract_docstring(code: str) -> str:
    match = re.search(r'(\"\"\"[\s\S]*?\"\"\"|\'\'\'[\s\S]*?\'\'\')', code)
    if match:
        return match.group(0).strip('"\' \n')
    return code