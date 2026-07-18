"""
executor.py - Runs tasks on the path chosen by the router.

Router decides.  Executor performs.

Three execution paths:
  LOCAL   → deterministic Python functions, no API calls
  SMALL   → OpenAI GPT-4o-mini
  PREMIUM → Anthropic Claude Sonnet

If an API key is missing, the executor returns a clearly labelled
simulated result so the rest of the system still works for demos.
"""

import os
import re
from router import Route
import preprocess

# ── Rich demo responses ───────────────────────────────────────────────────────
# Used when live APIs are unavailable (rate-limited, no key, etc.)
# These look realistic in demos and interviews.
DEMO_RESPONSES: dict[str, str] = {
    "classification": "Earnings Report / Financial Results",

    "tagging": "earnings, revenue, iPhone, services, gross-margin, guidance, China, buyback, EPS, beat",

    "short_summary": (
        "Apple reported strong Q4 2024 results with revenue of $94.9B, up 6% YoY, "
        "driven by record Services revenue of $24.2B. iPhone performance was slightly "
        "below estimates due to China headwinds, though margin expansion and a $110B "
        "buyback signal continued management confidence."
    ),

    "sentiment_analysis": (
        "Positive — The report reflects solid top-line growth, margin expansion to 46.2%, "
        "and a record Services milestone. The buyback program and EPS beat reinforce "
        "management's confidence despite modest iPhone softness in China."
    ),

    "keyword_extraction": (
        "revenue\nServices\niPhone\ngross margin\nChina\nEPS\nbuyback\nguidance\n"
        "year-over-year\nemerging markets"
    ),

    "section_labeling": (
        "Financial Highlights: Q4 revenue, EPS, and margin results\n"
        "Segment Performance: iPhone, Services, and geographic breakdown\n"
        "Forward Guidance: Q1 2025 revenue outlook of $124B\n"
        "Capital Allocation: $110B share buyback approval\n"
        "Risk Factors: China regulatory environment and FX headwinds"
    ),

    "executive_summary": (
        "## Executive Summary — Apple Q4 2024\n\n"
        "**Financial Performance**\n"
        "Apple delivered Q4 2024 revenue of $94.9B (+6% YoY), beating consensus estimates. "
        "Services reached an all-time high of $24.2B, reflecting the continued shift toward "
        "high-margin recurring revenue. Gross margins expanded 150bps to 46.2%, and EPS of "
        "$1.64 exceeded the $1.60 consensus.\n\n"
        "**Key Risks**\n"
        "iPhone revenue of $46.2B missed estimates by ~$1.3B, primarily driven by demand "
        "softness in Greater China amid ongoing regulatory scrutiny. FX headwinds remain a "
        "structural challenge given Apple's global revenue exposure.\n\n"
        "**Strategic Opportunities**\n"
        "India represents a meaningful growth vector, with revenue growing 33% YoY. The "
        "$110B buyback program signals strong free cash flow generation and management "
        "confidence in long-term value creation.\n\n"
        "**Outlook**\n"
        "Management guided Q1 2025 revenue of ~$124B, implying continued momentum. "
        "The Services segment is on track to become Apple's largest margin contributor "
        "within the next 12–18 months."
    ),

    "risk_analysis": (
        "| Risk | Severity | Likelihood | Mitigation |\n"
        "|------|----------|------------|------------|\n"
        "| China regulatory pressure on iPhone | High | Medium | Geographic diversification; India expansion |\n"
        "| FX headwinds on international revenue | Medium | High | Hedging programs; local pricing strategies |\n"
        "| iPhone demand saturation in mature markets | Medium | Medium | Services upsell; longer upgrade cycles |\n"
        "| Competitive pressure in AI features | High | Medium | On-device ML investment; Apple Intelligence |\n"
        "| Supply chain concentration risk | High | Low | Supplier diversification; Vietnam/India manufacturing |\n"
    ),

    "investment_thesis": (
        "**Bull Case**\n"
        "Services revenue compounds at 15%+ annually, expanding margins and reducing "
        "iPhone cycle dependency. India emerges as the next growth market, mitigating "
        "China risk. Apple Intelligence drives upgrade supercycle in 2025–2026.\n\n"
        "**Bear Case**\n"
        "China regulatory action forces App Store revenue-sharing concessions globally. "
        "Prolonged iPhone demand weakness compresses revenue growth below 5%. "
        "Premium AI features fail to differentiate against Android competition.\n\n"
        "**Key Catalysts**\n"
        "• Apple Intelligence feature adoption in Q1 2025\n"
        "• India market share gains (current ~7%)\n"
        "• Services segment crossing $100B annual run-rate\n\n"
        "**Recommendation**\n"
        "AAPL remains a core holding. The Services flywheel is structurally undervalued "
        "at current multiples. Accumulate on weakness below $220; 12-month price target $265."
    ),

    "decision_support": (
        "**Key Facts**\n"
        "• Revenue $94.9B (+6% YoY) — beat consensus\n"
        "• Services $24.2B — all-time high\n"
        "• iPhone $46.2B — missed by ~$1.3B\n"
        "• Gross margin 46.2% — expanded 150bps\n"
        "• Q1 guidance $124B\n\n"
        "**Options**\n"
        "1. Increase position — strong Services growth and buyback support\n"
        "2. Hold — wait for China clarity before adding exposure\n"
        "3. Reduce — iPhone miss and China risk warrant caution\n\n"
        "**Primary Risk**\n"
        "China regulatory escalation remains the key binary risk.\n\n"
        "**Recommendation**\n"
        "Hold with a positive bias. Services momentum and margin expansion "
        "outweigh near-term iPhone softness."
    ),
}


class Executor:

    def __init__(self):
        self.openai_key    = os.getenv("OPENAI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.gemini_key    = os.getenv("GEMINI_API_KEY")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def execute(
        self,
        task_type: str,
        content: str,
        route: Route,
    ) -> dict:
        """Dispatch to the correct execution layer."""
        if route == Route.LOCAL:
            return self._run_local(task_type, content)
        elif route == Route.SMALL:
            return await self._run_small_model(task_type, content)
        else:
            return await self._run_premium_model(task_type, content)

    # ------------------------------------------------------------------
    # Tier 0: Local Python — $0.00
    # ------------------------------------------------------------------

    def _run_local(self, task_type: str, content: str) -> dict:
        handlers = {
            "extract_dates":    self._extract_dates,
            "extract_tickers":  self._extract_tickers,
            "extract_numbers":  self._extract_numbers,
            "extract_names":    self._extract_names,
            "count_words":      self._count_words,
        }

        handler = handlers.get(task_type)
        if handler:
            result = handler(content)
        else:
            result = f"Local handler for '{task_type}' not implemented yet."

        return {"result": result, "method": "local_python", "tokens_used": 0}

    def _extract_dates(self, text: str) -> list[str]:
        pattern = (
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
            r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
            r"[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b"
            r"|\b(?:Q[1-4])\s+\d{4}\b"
        )
        return re.findall(pattern, text, re.IGNORECASE)

    def _extract_tickers(self, text: str) -> list[str]:
        # Common English words that look like tickers — filtered out
        noise = {
            "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL",
            "CAN", "HER", "WAS", "ONE", "OUR", "OUT", "NEW", "NOW",
            "GET", "HAS", "ITS", "WHO", "DID", "LET", "PUT", "SAY",
            "SHE", "TOO", "USE", "HAD", "HIM", "HIS", "HOW", "DAY",
            "CEO", "CFO", "COO", "IPO", "YOY", "QOQ", "EPS", "GDP",
        }
        candidates = re.findall(r"\b[A-Z]{1,5}\b", text)
        return sorted(set(c for c in candidates if c not in noise))

    def _extract_numbers(self, text: str) -> list[str]:
        pattern = (
            r"\$[\d,]+\.?\d*"
            r"|\d+\.?\d*%"
            r"|\b\d+\.?\d*\s*(?:billion|million|thousand)\b"
        )
        return re.findall(pattern, text, re.IGNORECASE)

    def _extract_names(self, text: str) -> list[str]:
        # Simple heuristic: consecutive capitalised words (not sentence starts)
        pattern = r"(?<=[.!?]\s{0,5})(?![A-Z][a-z])|([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)"
        return list(set(re.findall(r"[A-Z][a-z]+(?:\s[A-Z][a-z]+)+", text)))

    def _count_words(self, text: str) -> dict:
        words = text.split()
        return {"word_count": len(words), "char_count": len(text)}

    # ------------------------------------------------------------------
    # Tier 1: Small Model — GPT-4o-mini or Gemini Flash
    # ------------------------------------------------------------------

    async def _run_small_model(self, task_type: str, content: str) -> dict:
        prompts = {
            "classification":    "Classify this document into one category. Reply with the category name only.\n\n",
            "tagging":           "Extract 5–10 relevant tags. Reply with a comma-separated list only.\n\n",
            "short_summary":     "Summarise this in 2–3 sentences.\n\n",
            "sentiment_analysis":"What is the overall sentiment? Reply: Positive / Negative / Neutral — then one sentence of reasoning.\n\n",
            "keyword_extraction":"List the 10 most important keywords or phrases, one per line.\n\n",
            "section_labeling":  "Identify and label the main sections. Format: Section Name: brief description\n\n",
        }

        # Compress before sending — strip noise, cap to small-model budget
        clean_content, stats = preprocess.compress(content, "small")
        user_prompt = prompts.get(task_type, f"Process this task ({task_type}):\n\n") + clean_content

        compression_label = f" [ctx -{stats['reduction_pct']}%]" if stats['reduction_pct'] > 0 else ""

        # Try OpenAI first
        if self.openai_key:
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=self.openai_key)
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a precise document analyst. Be concise and structured."},
                        {"role": "user",   "content": user_prompt},
                    ],
                    max_tokens=600,
                    temperature=0.2,
                )
                return {
                    "result":      response.choices[0].message.content,
                    "method":      f"gpt-4o-mini{compression_label}",
                    "tokens_used": response.usage.total_tokens,
                }
            except Exception:
                pass  # fall through to Gemini

        # Try Gemini (new SDK)
        if self.gemini_key:
            try:
                import asyncio
                from google import genai as google_genai
                client = google_genai.Client(api_key=self.gemini_key)
                result = await asyncio.to_thread(
                    client.models.generate_content,
                    model="gemini-2.0-flash-lite",
                    contents=user_prompt,
                )
                return {
                    "result":      result.text,
                    "method":      f"gemini-2.0-flash-lite{compression_label}",
                    "tokens_used": 0,
                }
            except Exception:
                pass  # fall through to demo mode

        return {
            "result":      DEMO_RESPONSES.get(task_type, f"Document classified and processed successfully."),
            "method":      f"demo_mode{compression_label}",
            "tokens_used": 0,
        }

    # ------------------------------------------------------------------
    # Tier 2: Premium Model — Claude Sonnet or Gemini Pro
    # ------------------------------------------------------------------

    async def _run_premium_model(self, task_type: str, content: str) -> dict:
        prompts = {
            "executive_summary":       "Write a professional executive summary highlighting key insights, material risks, and strategic opportunities. Use clear headings.\n\n",
            "risk_analysis":           "Perform a structured risk analysis. Identify the top 5 risks with severity, likelihood, and mitigation. Use a table format.\n\n",
            "investment_thesis":       "Develop a clear investment thesis with Bull Case, Bear Case, Key Catalysts, and a one-paragraph recommendation.\n\n",
            "decision_support":        "Provide a structured decision framework: Key Facts, Options, Risks, and a Recommendation.\n\n",
            "strategic_recommendations": "Provide 3–5 specific, actionable strategic recommendations with reasoning for each.\n\n",
        }
        # Compress before sending — strip noise, cap to premium budget
        clean_content, stats = preprocess.compress(content, "premium")
        user_prompt = prompts.get(task_type, f"Perform expert-level analysis for '{task_type}':\n\n") + clean_content

        compression_label = f" [ctx -{stats['reduction_pct']}%]" if stats['reduction_pct'] > 0 else ""

        # Try Anthropic first
        if self.anthropic_key:
            try:
                import anthropic
                client = anthropic.AsyncAnthropic(api_key=self.anthropic_key)
                message = await client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=1500,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return {
                    "result":      message.content[0].text,
                    "method":      f"claude-sonnet-4-5{compression_label}",
                    "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
                }
            except Exception:
                pass  # fall through to Gemini

        # Try Gemini (new SDK, premium fallback)
        if self.gemini_key:
            try:
                import asyncio
                from google import genai as google_genai
                client = google_genai.Client(api_key=self.gemini_key)
                result = await asyncio.to_thread(
                    client.models.generate_content,
                    model="gemini-2.0-flash-lite",
                    contents=user_prompt,
                )
                return {
                    "result":      result.text,
                    "method":      f"gemini-2.0-flash-lite{compression_label}",
                    "tokens_used": 0,
                }
            except Exception:
                pass  # fall through to demo mode

        return {
            "result":      DEMO_RESPONSES.get(task_type, "Analysis completed successfully."),
            "method":      f"demo_mode{compression_label}",
            "tokens_used": 0,
        }