"""
router.py - Core routing logic for AI Cost Router

The router decides the cheapest execution path for each task:
  LOCAL   → Python functions, $0.00, ~5-15ms
  SMALL   → Cheap LLM (GPT-4o-mini), fractions of a cent, ~300-500ms
  PREMIUM → Claude Sonnet, ~$0.04+, ~1500-2500ms

Architecture note: ROUTING_RULES is the single source of truth.
Route, reason, and latency all live in one place — easy to extend
and easy to explain in interviews.

V1 uses deterministic rule-based routing. A future version could
introduce complexity scoring, token estimation, and quality/cost
tradeoff models based on observed execution telemetry.
"""

from dataclasses import dataclass
from enum import Enum


class Route(str, Enum):
    LOCAL   = "local"
    SMALL   = "small"
    PREMIUM = "premium"


@dataclass
class RoutingMetadata:
    route:      Route
    reason:     str
    latency_ms: int


# ── Single source of truth ────────────────────────────────────────────────────
# Every task type maps to a Route, a human-readable reason, and an estimated
# latency. Add new task types here — nothing else needs to change.
ROUTING_RULES: dict[str, RoutingMetadata] = {

    # ── LOCAL — deterministic Python, zero cost ───────────────────────────
    "extract_dates": RoutingMetadata(
        route=Route.LOCAL,
        reason="Date extraction is deterministic and solved with local regex — no LLM needed.",
        latency_ms=8,
    ),
    "extract_tickers": RoutingMetadata(
        route=Route.LOCAL,
        reason="Ticker extraction is deterministic pattern matching — no LLM needed.",
        latency_ms=12,
    ),
    "extract_numbers": RoutingMetadata(
        route=Route.LOCAL,
        reason="Numeric extraction (currency, percentages) uses local regex.",
        latency_ms=10,
    ),
    "extract_names": RoutingMetadata(
        route=Route.LOCAL,
        reason="Named-entity heuristics run locally without model inference.",
        latency_ms=15,
    ),
    "count_words": RoutingMetadata(
        route=Route.LOCAL,
        reason="Word and character counting is a string operation — zero inference cost.",
        latency_ms=2,
    ),
    "calculate_ratios": RoutingMetadata(
        route=Route.LOCAL,
        reason="Arithmetic ratios are computed locally with full precision.",
        latency_ms=5,
    ),
    "sentiment_score_keywords": RoutingMetadata(
        route=Route.LOCAL,
        reason="Keyword-based sentiment scoring uses a local lexicon — no model required.",
        latency_ms=20,
    ),

    # ── SMALL — language understanding without deep reasoning ─────────────
    "classification": RoutingMetadata(
        route=Route.SMALL,
        reason="Document classification requires language understanding but not deep reasoning.",
        latency_ms=400,
    ),
    "tagging": RoutingMetadata(
        route=Route.SMALL,
        reason="Tag extraction is a lightweight NLU task suited for a small model.",
        latency_ms=350,
    ),
    "short_summary": RoutingMetadata(
        route=Route.SMALL,
        reason="Brief summarisation (2-3 sentences) does not require premium reasoning.",
        latency_ms=450,
    ),
    "categorization": RoutingMetadata(
        route=Route.SMALL,
        reason="Category assignment is a classification task — small model is sufficient.",
        latency_ms=380,
    ),
    "sentiment_analysis": RoutingMetadata(
        route=Route.SMALL,
        reason="Sentiment classification with reasoning fits within a small model's capability.",
        latency_ms=420,
    ),
    "keyword_extraction": RoutingMetadata(
        route=Route.SMALL,
        reason="Keyword extraction is a lightweight NLU task.",
        latency_ms=360,
    ),
    "section_labeling": RoutingMetadata(
        route=Route.SMALL,
        reason="Identifying and labelling document sections is a structured NLU task.",
        latency_ms=430,
    ),

    # ── PREMIUM — synthesis, inference, expert judgment ───────────────────
    "executive_summary": RoutingMetadata(
        route=Route.PREMIUM,
        reason="Executive summarisation requires contextual synthesis and senior-level framing.",
        latency_ms=2200,
    ),
    "risk_analysis": RoutingMetadata(
        route=Route.PREMIUM,
        reason="Risk analysis demands multi-factor reasoning and domain expertise.",
        latency_ms=2400,
    ),
    "investment_thesis": RoutingMetadata(
        route=Route.PREMIUM,
        reason="Building an investment thesis requires deep financial reasoning and synthesis.",
        latency_ms=2600,
    ),
    "decision_support": RoutingMetadata(
        route=Route.PREMIUM,
        reason="Decision frameworks require weighing competing factors — premium reasoning needed.",
        latency_ms=2300,
    ),
    "complex_reasoning": RoutingMetadata(
        route=Route.PREMIUM,
        reason="Complex reasoning tasks are explicitly routed to the highest-capability model.",
        latency_ms=2500,
    ),
    "comprehensive_analysis": RoutingMetadata(
        route=Route.PREMIUM,
        reason="Comprehensive analysis requires sustained, multi-step reasoning.",
        latency_ms=2800,
    ),
    "strategic_recommendations": RoutingMetadata(
        route=Route.PREMIUM,
        reason="Strategic recommendations require synthesis of multiple evidence streams.",
        latency_ms=2400,
    ),
}

# Default for unknown task types — fail safe toward quality
_DEFAULT_ROUTING = RoutingMetadata(
    route=Route.PREMIUM,
    reason="Unknown task type — defaulting to premium model to ensure output quality.",
    latency_ms=2200,
)

# Cost per 1,000 tokens (input + output blended estimate)
COST_PER_1K_TOKENS: dict[Route, float] = {
    Route.LOCAL:   0.0,
    Route.SMALL:   0.000165,   # GPT-4o-mini
    Route.PREMIUM: 0.003,      # Claude Sonnet
}


# ── Router class ──────────────────────────────────────────────────────────────

class TaskRouter:

    def get_metadata(self, task_type: str) -> RoutingMetadata:
        """Return full routing metadata for a task type."""
        return ROUTING_RULES.get(task_type.lower().strip(), _DEFAULT_ROUTING)

    def route(self, task_type: str) -> Route:
        return self.get_metadata(task_type).route

    def estimate_cost(self, route: Route, content: str) -> float:
        if route == Route.LOCAL:
            return 0.0
        word_count = len(content.split())
        estimated_tokens = int(word_count / 0.75)
        return round((estimated_tokens / 1000) * COST_PER_1K_TOKENS[route], 6)

    def savings_vs_premium(self, actual_route: Route, content: str) -> float:
        premium_cost = self.estimate_cost(Route.PREMIUM, content)
        actual_cost  = self.estimate_cost(actual_route, content)
        return round(premium_cost - actual_cost, 6)

    # Convenience for the /routes endpoint
    @property
    def LOCAL_TASKS(self) -> list[str]:
        return [k for k, v in ROUTING_RULES.items() if v.route == Route.LOCAL]

    @property
    def SMALL_TASKS(self) -> list[str]:
        return [k for k, v in ROUTING_RULES.items() if v.route == Route.SMALL]

    @property
    def PREMIUM_TASKS(self) -> list[str]:
        return [k for k, v in ROUTING_RULES.items() if v.route == Route.PREMIUM]