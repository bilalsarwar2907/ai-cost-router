"""
models.py - Pydantic request/response schemas.

Keeping schemas in a separate file makes it easy to version the API
and swap out validation logic without touching business logic.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field
from router import Route


class AnalyzeRequest(BaseModel):
    task_type: str = Field(
        ...,
        description=(
            "The type of task to perform. "
            "Examples: extract_dates, classification, executive_summary"
        ),
        examples=["executive_summary"],
    )
    content: str = Field(
        ...,
        description="The text content to process.",
        examples=["Apple reported Q4 revenue of $94.9B, up 6% YoY..."],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "task_type": "executive_summary",
                    "content": (
                        "Apple Inc. reported record Q4 2024 revenue of $94.9 billion, "
                        "a 6% increase year-over-year. Services revenue reached $24.2B. "
                        "iPhone revenue declined slightly to $46.2B amid China headwinds."
                    ),
                }
            ]
        }
    }


class AnalyzeResponse(BaseModel):
    task_type: str
    route: Route = Field(description="Execution path chosen by the router")
    routing_reason: str = Field(description="Why the router chose this execution path")
    estimated_latency_ms: int = Field(description="Estimated execution latency in milliseconds")
    result: Any = Field(description="Output produced by the executor")
    estimated_cost_usd: float = Field(description="Estimated API cost in USD")
    savings_vs_premium_usd: float = Field(
        description="USD saved compared to routing everything to the premium model"
    )
    execution_method: str = Field(
        description="Actual method used: local_python, gpt-4o-mini, claude-sonnet-4-5, or simulated_*"
    )
    tokens_used: int = Field(description="Tokens consumed (0 for local execution)")


class RouteMapResponse(BaseModel):
    local_tasks: list[str]
    small_tasks: list[str]
    premium_tasks: list[str]
    cost_per_1k_tokens: dict[str, float]