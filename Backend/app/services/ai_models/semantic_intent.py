"""
Semantic Intent Model (Scam Markers) - flowchart steps 14-15.

Analyzes *what* the speaker says: transcribes the audio window (ASR) then
scores it for scam intent - urgency language, requests for OTPs/passwords,
impersonation of banks/government agencies, pressure tactics, etc.

======================================================================
 TEMPLATE / STUB - swap analyze() for a real model call before launch.
======================================================================
Real implementation will likely be two stages:
  1. ASR (speech-to-text), e.g. Whisper, a hosted ASR API, or a
     Filipino/Taglish-tuned ASR model (generic Whisper struggles with
     code-switched Taglish - worth benchmarking specifically for that).
  2. A scam-intent classifier/LLM prompt over the resulting transcript -
     this is presumably where the "Centry AI Chatbot (Localized LLM)"
     from the AI Analysis Layer comes in, or a separate lighter classifier
     if latency during a live call matters more than nuance.
"""

import random
from dataclasses import dataclass
from typing import Optional

MODEL_VERSION = "semantic-intent-stub-v0"

_SCAM_MARKER_POOL = [
    "urgency / time pressure",
    "requests OTP or password",
    "impersonates bank or government agency",
    "requests money transfer",
    "threatens account suspension",
    "asks to stay on the line / isolate from others",
]


@dataclass
class SemanticIntentOutput:
    scam_score: float  # 0-100, higher = more scam-like language
    detected_markers: list[str]
    transcript_snippet: Optional[str]
    model_version: str = MODEL_VERSION


async def analyze(audio_chunk: bytes, *, language_hint: str = "auto") -> SemanticIntentOutput:
    """
    language_hint: "en" | "fil" | "tgl" (Taglish) | "auto" - lets the caller
    (or a detected-language step upstream) bias ASR/classification, since
    Filipino MSME owners will often get scam calls in Taglish.

    STUB BEHAVIOR: returns a plausible-looking random score + a fake
    transcript so the pipeline is fully testable end-to-end.
    """
    if not audio_chunk:
        return SemanticIntentOutput(scam_score=0.0, detected_markers=[], transcript_snippet=None)

    # TODO: replace with real ASR + scam-intent classification, e.g.:
    #   transcript = await asr_client.transcribe(audio_chunk, language_hint)
    #   result = await scam_intent_classifier.classify(transcript)
    #   return SemanticIntentOutput(
    #       scam_score=result.scam_score,
    #       detected_markers=result.markers,
    #       transcript_snippet=transcript,
    #       model_version=result.model_version,
    #   )
    scam_score = round(random.uniform(5, 95), 1)
    marker_count = 1 if scam_score < 50 else random.randint(2, 3)
    detected_markers = random.sample(_SCAM_MARKER_POOL, k=min(marker_count, len(_SCAM_MARKER_POOL)))
    transcript_snippet = "[stub transcript - ASR not yet wired in]"
    return SemanticIntentOutput(
        scam_score=scam_score,
        detected_markers=detected_markers,
        transcript_snippet=transcript_snippet,
    )
