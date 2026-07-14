"""
Behavioral Trust Engine (Autonomous Response & Behavioral Engine box in the
flowchart) - flowchart steps 02-04, section 1 "Cross-Platform Monitoring".

Given raw activity telemetry pulled/pushed from a connected platform
(Shopee/Lazada/TikTok Shop/Meta - logins, transactions, listing changes,
messages, etc.), scores how much that activity deviates from the seller's
normal behavior and produces an updated trust score for the dashboard.

======================================================================
 TEMPLATE / STUB - swap process_event() for the AI team's real code.
======================================================================
Same idea as voice_biometrics.py / semantic_intent.py: this stub exists so
the plumbing around it (webhook ingestion, RabbitMQ publish, /ws/events
delivery to the dashboard) is fully wired and testable end-to-end *before*
the AI team's model is ready. The AI team's actual integration point is
`process_event()` below - keep its signature and `TrustScoreResult` shape
stable; everything upstream (app/routers/webhooks.py) and downstream
(the frontend, via /ws/events) is already built against that contract.

When the real implementation is ready, three ways to wire it in, roughly
in order of how much this file's shape should change:
  1. Simplest: replace the body of process_event() with a call into the AI
     team's Python code directly (import their package, call their
     function, map its output onto TrustScoreResult).
  2. If their model runs as its own service: replace the body with an
     httpx/gRPC call to that service instead.
  3. If it's heavier / shouldn't block the webhook response: have
     app/routers/webhooks.py hand off to a task queue (Celery/RQ/etc. -
     not set up yet) instead of awaiting this inline, and have that worker
     call process_event() (or the queue directly) when done.
"""

import random
import time
from dataclasses import dataclass, field

MODEL_VERSION = "behavioral-trust-engine-stub-v0"


@dataclass
class TrustScoreResult:
    trust_score: float  # 0-100, higher = more consistent with the seller's normal behavior
    risk_delta: float  # signed change vs. the previous score, for a "+/-N" UI indicator
    flagged_reasons: list[str] = field(default_factory=list)  # e.g. ["login from new device/region"]
    model_version: str = MODEL_VERSION
    latency_ms: int = 0


_FLAG_POOL = [
    "login from new device/region",
    "unusual transaction volume",
    "rapid listing/price changes",
    "multiple failed login attempts",
    "message pattern matches known scam script",
]


async def process_event(
    platform: str,
    event_type: str,
    payload: dict,
    *,
    previous_trust_score: float | None = None,
) -> TrustScoreResult:
    """
    platform: "SHOPEE" | "LAZADA" | "TIKTOK_SHOP" | "META" (see
        app.models.models.PlatformType).
    event_type: whatever the platform calls it in its webhook payload - a
        login event, an order/transaction event, a listing update, etc.
        Confirm the real event taxonomy with the AI team / each platform's
        webhook docs; not normalized yet since it's currently unused by the
        stub.
    payload: the raw (or lightly normalized) webhook body for that event.
    previous_trust_score: the seller's last known trust score, if any, so
        the real model can compute a meaningful delta / trend rather than
        scoring each event in isolation.

    STUB BEHAVIOR: returns a plausible-looking random score (mildly
    correlated with previous_trust_score so it doesn't visibly jump around
    on every call) so the webhook -> RabbitMQ -> /ws/events -> dashboard
    pipeline is fully testable end-to-end without a real model wired in.
    """
    started = time.perf_counter()

    # TODO: replace with a real call, e.g.:
    #   result = await behavioral_model_client.score(platform, event_type, payload,
    #                                                 previous_trust_score=previous_trust_score)
    #   return TrustScoreResult(
    #       trust_score=result.trust_score,
    #       risk_delta=result.trust_score - (previous_trust_score or result.trust_score),
    #       flagged_reasons=result.flagged_reasons,
    #       model_version=result.model_version,
    #       latency_ms=int((time.perf_counter() - started) * 1000),
    #   )
    baseline = previous_trust_score if previous_trust_score is not None else 80.0
    trust_score = round(max(0.0, min(100.0, baseline + random.uniform(-8, 5))), 1)
    risk_delta = round(trust_score - baseline, 1)
    flagged_reasons = random.sample(_FLAG_POOL, k=1) if trust_score < 60 else []

    latency_ms = int((time.perf_counter() - started) * 1000)
    return TrustScoreResult(
        trust_score=trust_score,
        risk_delta=risk_delta,
        flagged_reasons=flagged_reasons,
        latency_ms=latency_ms,
    )
