"""
main.py - FastAPI application entry point.

Run with:
    uvicorn main:app --reload

Then open:
    http://localhost:8000/docs   ← interactive Swagger UI
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from models import AnalyzeRequest, AnalyzeResponse, RouteMapResponse
from router import TaskRouter, Route, COST_PER_1K_TOKENS
from executor import Executor
from database import log_execution, get_history, get_analytics

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Cost Router",
    description=(
        "Intelligent task routing that selects the cheapest execution path "
        "(local Python → small LLM → premium LLM) capable of producing "
        "acceptable quality. Tracks cost savings on every request."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singletons — initialised once, shared across requests
router   = TaskRouter()
executor = Executor()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["health"])
def root():
    """Health check."""
    return {
        "status": "ok",
        "message": "AI Cost Router is running",
        "docs": "/docs",
        "version": "0.2.0",
    }


@app.post("/analyze", response_model=AnalyzeResponse, tags=["routing"])
async def analyze(request: AnalyzeRequest):
    """
    Submit a task for cost-aware routing and execution.

    The router selects the cheapest execution tier that can handle the task:
    - **LOCAL**   → deterministic Python, $0.00
    - **SMALL**   → Gemini Flash, fractions of a cent
    - **PREMIUM** → Claude Sonnet, ~$0.003+

    The response includes the routing decision, result, and cost comparison.
    """
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="content must not be empty")
    if not request.task_type.strip():
        raise HTTPException(status_code=400, detail="task_type must not be empty")

    # 1. Routing decision
    metadata       = router.get_metadata(request.task_type)
    route          = metadata.route
    estimated_cost = router.estimate_cost(route, request.content)
    savings        = router.savings_vs_premium(route, request.content)

    # 2. Execute on chosen tier
    execution_result = await executor.execute(
        task_type=request.task_type,
        content=request.content,
        route=route,
    )

    response = AnalyzeResponse(
        task_type=request.task_type,
        route=route,
        routing_reason=metadata.reason,
        estimated_latency_ms=metadata.latency_ms,
        result=execution_result["result"],
        estimated_cost_usd=estimated_cost,
        savings_vs_premium_usd=savings,
        execution_method=execution_result["method"],
        tokens_used=execution_result.get("tokens_used", 0),
    )

    # 3. Log to DB (fire-and-forget — never blocks or crashes the response)
    await log_execution({
        "task_type":              response.task_type,
        "route":                  response.route.value,
        "routing_reason":         response.routing_reason,
        "estimated_cost_usd":     response.estimated_cost_usd,
        "savings_vs_premium_usd": response.savings_vs_premium_usd,
        "estimated_latency_ms":   response.estimated_latency_ms,
        "tokens_used":            response.tokens_used,
        "execution_method":       response.execution_method,
    })

    return response


@app.get("/routes", response_model=RouteMapResponse, tags=["routing"])
def get_route_map():
    """
    Returns the full routing map — which task types go to which tier.
    Useful for building a frontend that pre-labels tasks before submission.
    """
    return RouteMapResponse(
        local_tasks=sorted(router.LOCAL_TASKS),
        small_tasks=sorted(router.SMALL_TASKS),
        premium_tasks=sorted(router.PREMIUM_TASKS),
        cost_per_1k_tokens={
            route.value: cost
            for route, cost in COST_PER_1K_TOKENS.items()
        },
    )


@app.post("/batch", tags=["routing"])
async def batch_analyze(requests: list[AnalyzeRequest]):
    """
    Submit multiple tasks at once.
    Returns individual routing decisions + a cost summary across all tasks.

    This endpoint demonstrates the aggregate savings clearly —
    the kind of number that goes in the dashboard's 'Savings' card.
    """
    if not requests:
        raise HTTPException(status_code=400, detail="requests list must not be empty")
    if len(requests) > 20:
        raise HTTPException(status_code=400, detail="max 20 tasks per batch")

    results       = []
    total_cost    = 0.0
    total_savings = 0.0

    for req in requests:
        metadata       = router.get_metadata(req.task_type)
        route          = metadata.route
        estimated_cost = router.estimate_cost(route, req.content)
        savings        = router.savings_vs_premium(route, req.content)

        execution_result = await executor.execute(
            task_type=req.task_type,
            content=req.content,
            route=route,
        )

        task_response = AnalyzeResponse(
            task_type=req.task_type,
            route=route,
            routing_reason=metadata.reason,
            estimated_latency_ms=metadata.latency_ms,
            result=execution_result["result"],
            estimated_cost_usd=estimated_cost,
            savings_vs_premium_usd=savings,
            execution_method=execution_result["method"],
            tokens_used=execution_result.get("tokens_used", 0),
        )
        results.append(task_response)
        total_cost    += estimated_cost
        total_savings += savings

        # Log each task individually — gives granular per-task history
        await log_execution({
            "task_type":              task_response.task_type,
            "route":                  task_response.route.value,
            "routing_reason":         task_response.routing_reason,
            "estimated_cost_usd":     task_response.estimated_cost_usd,
            "savings_vs_premium_usd": task_response.savings_vs_premium_usd,
            "estimated_latency_ms":   task_response.estimated_latency_ms,
            "tokens_used":            task_response.tokens_used,
            "execution_method":       task_response.execution_method,
        })

    premium_equivalent = total_cost + total_savings
    savings_pct = (
        (total_savings / premium_equivalent * 100)
        if premium_equivalent > 0
        else 0.0
    )

    return {
        "tasks": results,
        "summary": {
            "total_tasks":             len(results),
            "total_cost_usd":          round(total_cost, 6),
            "cost_if_all_premium_usd": round(premium_equivalent, 6),
            "total_savings_usd":       round(total_savings, 6),
            "savings_percent":         round(savings_pct, 1),
        },
    }


# ---------------------------------------------------------------------------
# History & Analytics  (Sprint 3)
# ---------------------------------------------------------------------------

@app.get("/history", tags=["analytics"])
async def execution_history(limit: int = Query(default=50, ge=1, le=500)):
    """
    Returns the most recent task executions logged to the database.
    Supports multi-tenancy via tenant_id (all tenants returned for now).
    """
    rows = await get_history(limit)
    return {"executions": rows, "count": len(rows)}


@app.get("/analytics", tags=["analytics"])
async def analytics():
    """
    Returns aggregate cost and savings statistics:
    - All-time totals (tasks, cost, savings, savings %)
    - Breakdown by execution tier (local / small / premium)
    - Daily savings for the last 30 days (for the time-series chart)
    """
    return await get_analytics()
