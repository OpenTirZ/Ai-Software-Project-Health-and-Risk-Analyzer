"""
Reusable LLM Client — AI Software Project Health & Risk Analyzer
-----------------------------------------------------------------
Provides a single, project-wide gateway to external LLM services.

Supported backends (resolved at runtime from environment variables):
  1. Google Gemini   — enabled when GEMINI_API_KEY is set.
  2. OpenRouter      — enabled when OPENROUTER_API_KEY is set
                       (OpenAI-compatible chat-completions endpoint).

Environment Variables
---------------------
GEMINI_API_KEY          : Google Gemini API key (preferred when set).
GEMINI_MODEL            : Gemini model name (default: gemini-1.5-flash).
OPENROUTER_API_KEY      : OpenRouter API key.
OPENROUTER_MODEL        : OpenRouter model (default: openai/gpt-4o-mini).
LLM_TIMEOUT_SECONDS     : Request timeout in seconds (default: 30).

Design Principles
-----------------
- Credentials are read exclusively from environment variables — never hardcoded.
- Typed exceptions are raised for every error class so callers can apply
  grounded fallback logic.
- The module is intentionally standalone: it does NOT import from
  recommendation_service.py and does NOT touch LangGraph.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"
_DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"
_DEFAULT_TIMEOUT = 30

_HTTP_REFERER = "https://github.com/OpenTirZ/Ai-Software-Project-Health-and-Risk-Analyzer"
_X_TITLE = "AI Software Project Health and Risk Analyzer"


# ---------------------------------------------------------------------------
# Typed Exceptions
# ---------------------------------------------------------------------------

class LLMClientError(Exception):
    """Base class for all LLM client errors."""


class LLMMissingCredentialsError(LLMClientError):
    """Raised when no API key is configured for any supported backend."""


class LLMAPIError(LLMClientError):
    """Raised when the upstream API returns a non-success HTTP response."""


class LLMTimeoutError(LLMClientError):
    """Raised when the upstream API request times out."""


class LLMEmptyResponseError(LLMClientError):
    """Raised when the LLM returns an empty or whitespace-only response."""


# ---------------------------------------------------------------------------
# Optional Gemini SDK support
# ---------------------------------------------------------------------------

def _try_import_genai():
    """
    Attempt to import the google-generativeai SDK.
    Returns the module if available, None otherwise.
    The SDK is optional; if absent, Gemini is simply unavailable.
    """
    try:
        import google.generativeai as genai  # type: ignore[import]
        return genai
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Backend call helpers
# ---------------------------------------------------------------------------

def _call_gemini(prompt: str, api_key: str, model: str, timeout: int) -> str:
    """
    Call the Google Gemini API using the official SDK.

    Raises:
        LLMClientError: If the SDK is not installed.
        LLMAPIError: If the API returns an error.
        LLMTimeoutError: If the request times out.
        LLMEmptyResponseError: If the response content is empty.
    """
    genai = _try_import_genai()
    if genai is None:
        raise LLMClientError(
            "google-generativeai package is not installed. "
            "Install it with: pip install google-generativeai"
        )

    try:
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel(model)
        # The SDK does not natively support a timeout kwarg in generate_content,
        # so we wrap it with a requests-style timeout using a thread approach.
        # For simplicity and reliability, we use the SDK's default behaviour and
        # catch deadline/timeout exceptions by their type name.
        response = gemini_model.generate_content(prompt)
        content = response.text if hasattr(response, "text") else ""
        if not content or not content.strip():
            raise LLMEmptyResponseError("Gemini returned an empty response.")
        return content.strip()
    except LLMEmptyResponseError:
        raise
    except Exception as exc:
        exc_name = type(exc).__name__.lower()
        if "timeout" in exc_name or "deadline" in exc_name:
            raise LLMTimeoutError(f"Gemini API timed out: {exc}") from exc
        raise LLMAPIError(f"Gemini API error: {exc}") from exc


def _call_openrouter(prompt: str, api_key: str, model: str, timeout: int) -> str:
    """
    Call an OpenAI-compatible chat-completions endpoint via OpenRouter.

    Raises:
        LLMAPIError: If the HTTP request fails (non-2xx) or response is malformed.
        LLMTimeoutError: If the request times out.
        LLMEmptyResponseError: If the response content is empty.
    """
    try:
        response = requests.post(
            _OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": _HTTP_REFERER,
                "X-Title": _X_TITLE,
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Return valid JSON only. "
                            "All outputs are advisory and informational; "
                            "you must never claim to perform automated actions."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=timeout,
        )
    except requests.exceptions.Timeout as exc:
        raise LLMTimeoutError(f"OpenRouter request timed out after {timeout}s.") from exc
    except requests.exceptions.RequestException as exc:
        raise LLMAPIError(f"OpenRouter request failed: {exc}") from exc

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise LLMAPIError(
            f"OpenRouter returned HTTP {response.status_code}: {response.text[:500]}"
        ) from exc

    try:
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMAPIError(
            f"Unexpected OpenRouter response structure: {exc}. "
            f"Raw (first 300 chars): {response.text[:300]}"
        ) from exc

    if not content or not content.strip():
        raise LLMEmptyResponseError("OpenRouter returned an empty message content.")

    return content.strip()


# ---------------------------------------------------------------------------
# Public Client Class
# ---------------------------------------------------------------------------

class LLMClient:
    """
    Project-wide LLM gateway.

    Backend selection priority:
      1. Gemini  — if GEMINI_API_KEY is set and google-generativeai is installed.
      2. OpenRouter — if OPENROUTER_API_KEY is set.

    Both keys may be set; Gemini is preferred when available.

    Args:
        gemini_api_key: Override GEMINI_API_KEY (for testing).
        openrouter_api_key: Override OPENROUTER_API_KEY (for testing).
        gemini_model: Override GEMINI_MODEL.
        openrouter_model: Override OPENROUTER_MODEL.
        timeout: HTTP timeout in seconds (overrides LLM_TIMEOUT_SECONDS).
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        gemini_model: Optional[str] = None,
        openrouter_model: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self._gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY") or ""
        self._openrouter_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY") or ""
        self._gemini_model = (
            gemini_model
            or os.getenv("GEMINI_MODEL")
            or _DEFAULT_GEMINI_MODEL
        )
        self._openrouter_model = (
            openrouter_model
            or os.getenv("OPENROUTER_MODEL")
            or _DEFAULT_OPENROUTER_MODEL
        )
        try:
            self._timeout = int(
                timeout
                if timeout is not None
                else os.getenv("LLM_TIMEOUT_SECONDS", str(_DEFAULT_TIMEOUT))
            )
        except (ValueError, TypeError):
            self._timeout = _DEFAULT_TIMEOUT

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def gemini_available(self) -> bool:
        """True if Gemini credentials are configured and SDK is installed."""
        return bool(self._gemini_key) and _try_import_genai() is not None

    @property
    def openrouter_available(self) -> bool:
        """True if OpenRouter credentials are configured."""
        return bool(self._openrouter_key)

    @property
    def any_backend_available(self) -> bool:
        """True if at least one LLM backend is configured."""
        return self.gemini_available or self.openrouter_available

    # ------------------------------------------------------------------
    # Public chat interface
    # ------------------------------------------------------------------

    def chat(self, prompt: str) -> str:
        """
        Send a prompt to the best available LLM backend and return the raw
        text response.

        Backend selection:
          Gemini is tried first (if configured and SDK present),
          then OpenRouter.

        Args:
            prompt: The full prompt string to send.

        Returns:
            Raw text response from the LLM.

        Raises:
            LLMMissingCredentialsError: If no backend is configured.
            LLMAPIError: If the API call fails.
            LLMTimeoutError: If the request times out.
            LLMEmptyResponseError: If the response is empty.
        """
        if not prompt or not prompt.strip():
            raise ValueError("prompt must be a non-empty string.")

        if self.gemini_available:
            logger.debug("LLMClient: using Gemini backend (%s).", self._gemini_model)
            return _call_gemini(
                prompt, self._gemini_key, self._gemini_model, self._timeout
            )

        if self.openrouter_available:
            logger.debug("LLMClient: using OpenRouter backend (%s).", self._openrouter_model)
            return _call_openrouter(
                prompt, self._openrouter_key, self._openrouter_model, self._timeout
            )

        raise LLMMissingCredentialsError(
            "No LLM backend is configured. "
            "Set GEMINI_API_KEY (and install google-generativeai) "
            "or OPENROUTER_API_KEY in your environment."
        )


# ---------------------------------------------------------------------------
# Module-level convenience instance
# ---------------------------------------------------------------------------

def get_default_client() -> LLMClient:
    """
    Return a new LLMClient initialised from environment variables.
    Callers may also instantiate LLMClient directly for testing.
    """
    return LLMClient()
