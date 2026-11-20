"""
Backend AI module: Prompt security boundaries and structured output schemas.
"""

from Backend.ai.prompt_guard import (
    InjectionCheckResult,
    LLMJsonDecodeError,
    LLMOutputError,
    LLMOutputValidationError,
    PromptGuard,
    detect_prompt_injection,
    parse_and_validate_llm_json,
    sanitize_commit_message,
    sanitize_github_payload,
    sanitize_issue_details,
    sanitize_pr_details,
    sanitize_text,
    wrap_untrusted_content,
)
from Backend.ai.schemas import (
    ExplanationSchema,
    RecommendationSchema,
    ReportResponseSchema,
)

__all__ = [
    "PromptGuard",
    "InjectionCheckResult",
    "sanitize_text",
    "detect_prompt_injection",
    "wrap_untrusted_content",
    "sanitize_commit_message",
    "sanitize_pr_details",
    "sanitize_issue_details",
    "sanitize_github_payload",
    "parse_and_validate_llm_json",
    "LLMOutputError",
    "LLMJsonDecodeError",
    "LLMOutputValidationError",
    "ExplanationSchema",
    "RecommendationSchema",
    "ReportResponseSchema",
]

