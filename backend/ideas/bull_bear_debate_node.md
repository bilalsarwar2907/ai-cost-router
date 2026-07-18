# Idea: Bull vs. Bear Financial Debate Node

Source: TauricResearch/TradingAgents pattern analysis
Status: Not started — candidate for Sprint 4+

---

## The Concept

Instead of asking a premium model "Should I buy AAPL?", spin up two
parallel instances with opposing mandates, force a structured debate,
then synthesise the output.

Maps directly onto the existing 3-tier router:

```
User input: "Analyse AAPL earnings"
        │
        ▼
┌─────────────────────────────────┐
│  LOCAL tier (parallel, $0.00)  │
│  - extract_tickers              │
│  - extract_numbers              │
│  - extract_dates                │
└────────────┬────────────────────┘
             │  cleaned, compressed data arrays
             ▼
┌──────────────────────┐   ┌──────────────────────┐
│  SMALL tier          │   │  SMALL tier          │
│  Bull Researcher     │   │  Bear Researcher     │
│  (sentiment_analysis │   │  (risk_analysis      │
│   + keyword_extract) │   │   + section_labeling)│
└──────────┬───────────┘   └──────────┬───────────┘
           │  bull_brief              │  bear_brief
           └────────────┬─────────────┘
                        ▼
          ┌─────────────────────────┐
          │  PREMIUM tier           │
          │  Debate Synthesiser     │
          │  (investment_thesis)    │
          │  Reads both briefs,     │
          │  issues final verdict   │
          └─────────────────────────┘
```

## Why it fits the project

- Demonstrates multi-step agentic workflows on the existing router
- LOCAL pre-processing already strips noise before anything hits an LLM
- SMALL handles the analyst nodes cheaply (2 parallel calls ~$0.0004 total)
- PREMIUM only runs once on curated, debated data — not raw text
- Cost savings story becomes even stronger: complex financial reasoning
  for a fraction of what a single raw premium call would cost

## Implementation sketch

New task types to add to ROUTING_RULES:
  - `bull_analysis`  → SMALL
  - `bear_analysis`  → SMALL
  - `debate_synthesis` → PREMIUM

New endpoint: POST /debate
  - Accepts: content + ticker
  - Runs LOCAL extraction, then bull + bear in parallel (asyncio.gather)
  - Feeds both outputs to PREMIUM synthesiser
  - Returns: bull_brief, bear_brief, final_verdict, total_cost, savings

## Interview value

Answers: "How would you extend this for financial use cases?"
Shows:   Multi-agent orchestration, parallel execution, cost-aware
         routing across a full agentic pipeline — not just single tasks.

## What to ignore from the TradingAgents repo

- Their UI/CLI (ours is better)
- Their hardcoded LangGraph configs (we use dynamic routing rules)
- Their model choices (they blindly use gpt-4o/o1 — no cost awareness)
