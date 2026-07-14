"""
Aggregates the parallel Voice Biometrics + Semantic Intent outputs into a
single risk score/level (flowchart step 16: "Aggregate metrics into raw
risk assessment"). Kept separate from the model stubs so the weighting
logic can be tuned independently of whichever models end up behind them.
"""

from app.models.models import RiskLevel
from app.services.ai_models.voice_biometrics import VoiceBiometricsOutput
from app.services.ai_models.semantic_intent import SemanticIntentOutput

# TODO: tune these once real model score distributions are known. Semantic
# intent is weighted higher here on the assumption that *what* a caller
# asks for (e.g. "give me your OTP") is a stronger scam signal than *how*
# they sound, but this should be validated against labeled call data.
VOICE_WEIGHT = 0.4
SEMANTIC_WEIGHT = 0.6

# Score thresholds for mapping aggregated_risk_score -> RiskLevel.
_LEVEL_THRESHOLDS: list[tuple[float, RiskLevel]] = [
    (85, RiskLevel.CRITICAL),
    (65, RiskLevel.HIGH),
    (35, RiskLevel.MEDIUM),
    (0, RiskLevel.LOW),
]

# Section 3 of the flowchart: "High-Risk Scam / Breach Detected" triggers
# the autonomous block flow. This is the score above which that should fire.
AUTONOMOUS_BLOCK_THRESHOLD = 85


def _score_to_level(score: float) -> RiskLevel:
    for threshold, level in _LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return RiskLevel.LOW


def aggregate(voice: VoiceBiometricsOutput, semantic: SemanticIntentOutput) -> tuple[float, RiskLevel, bool]:
    """
    Combines a low authenticity_score (voice likely fake) and a high
    scam_score (language sounds like a scam) into one 0-100 risk score.

    voice.authenticity_score is inverted here (100 - score) since it's
    scored in the opposite direction from risk: high authenticity = low risk.

    Returns (aggregated_risk_score, aggregated_risk_level, recommend_autonomous_block).
    """
    voice_risk_component = 100 - voice.authenticity_score
    semantic_risk_component = semantic.scam_score

    aggregated_score = round(
        (voice_risk_component * VOICE_WEIGHT) + (semantic_risk_component * SEMANTIC_WEIGHT), 1
    )
    aggregated_score = max(0.0, min(100.0, aggregated_score))

    level = _score_to_level(aggregated_score)
    recommend_block = aggregated_score >= AUTONOMOUS_BLOCK_THRESHOLD

    return aggregated_score, level, recommend_block
