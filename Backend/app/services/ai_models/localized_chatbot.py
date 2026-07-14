"""
Centry AI Chatbot (Localized LLM) - flowchart steps 28-31.

Given a user's question plus grounding context pulled from their incident
history (RiskAssessment rows on a VerificationSession), produces a
human-readable, localized (English / Filipino / Taglish) explanation of
what happened and what to do next.

======================================================================
 TEMPLATE / STUB - swap generate_reply() for a real model call before launch.
======================================================================
Wire this up to whichever localized LLM the AI team lands on - could be a
fine-tuned open-weight model self-hosted for data-residency reasons (PH
MSME financial data), or a hosted LLM API with a strong localization
system prompt. Keep the `generate_reply` contract stable.
"""

import time
from dataclasses import dataclass
from typing import Optional

MODEL_VERSION = "centry-chatbot-localized-llm-stub-v0"

_SUPPORTED_LANGUAGES = {"en", "fil", "tgl"}


@dataclass
class ChatbotReply:
    content: str
    language: str
    model_version: str = MODEL_VERSION
    latency_ms: int = 0


def _stub_reply_text(user_message: str, language: str, incident_summary: Optional[str]) -> str:
    context_line = f" Based on your recent call (risk context: {incident_summary})," if incident_summary else ""
    if language == "fil":
        return (
            f"[STUB - LLM hindi pa nakakonekta]{context_line} narito ang paliwanag: "
            f"'{user_message}' ay tatanggapin ng aktwal na localized na modelo dito."
        )
    if language == "tgl":
        return (
            f"[STUB - LLM not yet connected]{context_line} here's the explanation pero this "
            f"is placeholder lang: '{user_message}' will be handled by the real localized model here."
        )
    return (
        f"[STUB - LLM not yet connected]{context_line} here's a placeholder explanation for: "
        f"'{user_message}'. The real localized model will generate the actual answer here."
    )


async def generate_reply(
    user_message: str,
    *,
    language: str = "en",
    incident_summary: Optional[str] = None,
) -> ChatbotReply:
    """
    user_message: the MSME owner's latest chat message.
    language: "en" | "fil" | "tgl" - which language to respond in.
    incident_summary: short plain-text summary of the relevant
        RiskAssessment/VerificationSession rows, built by chat_service and
        passed in here as grounding context (flowchart step 29 - "query
        incident logs for context").

    STUB BEHAVIOR: returns a canned, clearly-labeled placeholder reply so
    the chat endpoints are fully testable end-to-end before a real
    localized LLM is wired in.
    """
    started = time.perf_counter()
    language = language if language in _SUPPORTED_LANGUAGES else "en"

    # TODO: replace with a real call, e.g.:
    #   response = await localized_llm_client.chat(
    #       messages=[...history..., {"role": "user", "content": user_message}],
    #       system_prompt=LOCALIZED_SYSTEM_PROMPT.format(language=language),
    #       context=incident_summary,
    #   )
    #   content = response.text
    content = _stub_reply_text(user_message, language, incident_summary)

    latency_ms = int((time.perf_counter() - started) * 1000)
    return ChatbotReply(content=content, language=language, latency_ms=latency_ms)
