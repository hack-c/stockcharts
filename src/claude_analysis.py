"""Claude API integration with Edwards & Magee technical analysis prompt."""

import asyncio
import base64
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import anthropic
from anthropic import AsyncAnthropic

from .utils import ensure_env_vars, async_retry

logger = logging.getLogger("stockcharts")

EDWARDS_MAGEE_PROMPT = """You are an expert technical analyst trained in Edwards & Magee's "Technical Analysis of Stock Trends" (5th Edition) methodology. You are provided with multiple chart images for the same stock:
- DAILY candlestick chart with RSI indicator
- WEEKLY candlestick chart with RSI indicator
- DAILY Point & Figure (P&F) chart
- WEEKLY Point & Figure (P&F) chart

Edwards & Magee devoted considerable attention to Point & Figure charts for identifying support/resistance levels and calculating price targets. Use the P&F charts to identify key price levels, breakouts, and potential price objectives.

Analyze all charts together to provide a comprehensive technical analysis.

## Analysis Framework (Edwards & Magee 5th Edition)

### 1. TREND ANALYSIS
Identify the current trends following Dow Theory principles:
- **Primary Trend**: The major trend (bullish/bearish) lasting months to years
- **Secondary Trend**: Intermediate corrections against the primary trend (weeks to months)
- **Minor Trend**: Short-term fluctuations (days to weeks)
- **Trendlines**: Draw mental trendlines connecting significant lows (uptrend) or highs (downtrend)
- **Channels**: Note if price is moving within parallel trend channel lines

### 2. CHART PATTERNS
Look for classical patterns as defined in the 5th edition:

**Reversal Patterns:**
- Head and Shoulders (regular and inverse)
- Double Tops and Double Bottoms
- Triple Tops and Triple Bottoms
- Rounding Tops and Rounding Bottoms (saucers)
- V-Formations and Inverted V-Formations

**Continuation Patterns:**
- Symmetrical Triangles
- Ascending Triangles (bullish)
- Descending Triangles (bearish)
- Rectangles (trading ranges)
- Flags and Pennants
- Wedges (rising and falling)

### 3. SUPPORT AND RESISTANCE
- Identify key horizontal support levels from prior lows
- Identify key horizontal resistance levels from prior highs
- Note any breakouts or breakdowns from these levels
- Volume confirmation is critical for valid breakouts (5th ed. emphasis)

### 4. VOLUME ANALYSIS
Per Edwards & Magee's emphasis on volume:
- Volume should confirm price movements
- Breakouts should occur on expanding volume
- Declining volume during consolidation is normal
- Volume divergences may signal trend weakness

### 5. RSI INDICATOR ANALYSIS (Modern Overlay)
- Current RSI value and zone (overbought >70, oversold <30, neutral 30-70)
- RSI divergences with price (bullish/bearish)
- RSI trend and momentum

### 6. RECOMMENDATION
Provide a clear trading recommendation:
- **Signal**: BUY, SELL, or HOLD
- **Confidence**: HIGH, MEDIUM, or LOW
- **Reasoning**: Brief explanation based on the above analysis

## Response Format

Respond with a JSON object in the following structure:
```json
{
  "symbol": "TICKER",
  "analysis_date": "YYYY-MM-DD",
  "primary_trend": "BULLISH|BEARISH|NEUTRAL",
  "secondary_trend": "BULLISH|BEARISH|NEUTRAL",
  "patterns_identified": [
    {
      "pattern": "Pattern Name",
      "type": "REVERSAL|CONTINUATION",
      "implication": "BULLISH|BEARISH",
      "completion": "FORMING|COMPLETE|BROKEN"
    }
  ],
  "support_levels": [price1, price2],
  "resistance_levels": [price1, price2],
  "volume_assessment": "CONFIRMING|DIVERGING|NEUTRAL",
  "rsi": {
    "value": 55,
    "zone": "NEUTRAL|OVERBOUGHT|OVERSOLD",
    "divergence": "NONE|BULLISH|BEARISH"
  },
  "recommendation": {
    "signal": "BUY|SELL|HOLD",
    "confidence": "HIGH|MEDIUM|LOW",
    "reasoning": "Brief explanation"
  },
  "key_observations": [
    "Observation 1",
    "Observation 2",
    "Observation 3"
  ],
  "summary": "2-3 sentence actionable summary based on classical Edwards & Magee methodology."
}
```

Analyze the chart now and provide your assessment."""


@dataclass
class AnalysisResult:
    """Structured result from Claude's chart analysis."""

    symbol: str
    analysis_date: str
    primary_trend: str
    secondary_trend: str
    patterns_identified: list[dict]
    support_levels: list[float]
    resistance_levels: list[float]
    volume_assessment: str
    rsi: dict
    recommendation: dict
    key_observations: list[str]
    summary: str
    raw_response: str


class ClaudeAnalyzer:
    """Analyzes stock charts using Claude API with async support."""

    def __init__(self, config: dict):
        """
        Initialize Claude analyzer.

        Args:
            config: Analysis configuration dictionary
        """
        self.config = config.get("analysis", {})
        self.model = self.config.get("model", "claude-sonnet-4-20250514")
        self.max_tokens = self.config.get("max_tokens", 2000)

        # Load API key and create async client
        env_vars = ensure_env_vars("ANTHROPIC_API_KEY")
        self.client = AsyncAnthropic(api_key=env_vars["ANTHROPIC_API_KEY"])

    def _load_image_base64(self, image_path: Path) -> str:
        """Load an image file and convert to base64."""
        with open(image_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")

    def _parse_response(self, response_text: str, symbol: str) -> AnalysisResult:
        """
        Parse Claude's response into structured data.

        Args:
            response_text: Raw response from Claude
            symbol: Stock ticker symbol

        Returns:
            Parsed AnalysisResult
        """
        # Try to extract JSON from the response
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return AnalysisResult(
                    symbol=data.get("symbol", symbol),
                    analysis_date=data.get("analysis_date", ""),
                    primary_trend=data.get("primary_trend", "NEUTRAL"),
                    secondary_trend=data.get("secondary_trend", "NEUTRAL"),
                    patterns_identified=data.get("patterns_identified", []),
                    support_levels=data.get("support_levels", []),
                    resistance_levels=data.get("resistance_levels", []),
                    volume_assessment=data.get("volume_assessment", "NEUTRAL"),
                    rsi=data.get("rsi", {}),
                    recommendation=data.get("recommendation", {}),
                    key_observations=data.get("key_observations", []),
                    summary=data.get("summary", ""),
                    raw_response=response_text,
                )
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response: {e}")

        # Fallback: return basic result with raw response
        return AnalysisResult(
            symbol=symbol,
            analysis_date="",
            primary_trend="UNKNOWN",
            secondary_trend="UNKNOWN",
            patterns_identified=[],
            support_levels=[],
            resistance_levels=[],
            volume_assessment="UNKNOWN",
            rsi={},
            recommendation={"signal": "HOLD", "confidence": "LOW", "reasoning": "Unable to parse analysis"},
            key_observations=[],
            summary=response_text[:500] if len(response_text) > 500 else response_text,
            raw_response=response_text,
        )

    @async_retry(max_attempts=3, delay=2.0, exceptions=(anthropic.APIError,))
    async def analyze(self, image_paths: dict[str, Path], symbol: str) -> AnalysisResult:
        """
        Analyze daily and weekly chart images using Claude.

        Args:
            image_paths: Dict with 'daily' and/or 'weekly' paths to chart screenshots
            symbol: Stock ticker symbol

        Returns:
            AnalysisResult with structured analysis data
        """
        logger.info(f"Analyzing charts for {symbol}")

        # Build content list with images
        content = []

        # Add daily chart if available
        if "daily" in image_paths and image_paths["daily"].exists():
            daily_data = self._load_image_base64(image_paths["daily"])
            content.append({
                "type": "text",
                "text": "DAILY CHART:",
            })
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": daily_data,
                },
            })

        # Add weekly chart if available
        if "weekly" in image_paths and image_paths["weekly"].exists():
            weekly_data = self._load_image_base64(image_paths["weekly"])
            content.append({
                "type": "text",
                "text": "WEEKLY CHART:",
            })
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": weekly_data,
                },
            })

        # Add P&F daily chart if available
        if "pnf_daily" in image_paths and image_paths["pnf_daily"].exists():
            pnf_daily_data = self._load_image_base64(image_paths["pnf_daily"])
            content.append({
                "type": "text",
                "text": "POINT & FIGURE DAILY CHART:",
            })
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": pnf_daily_data,
                },
            })

        # Add P&F weekly chart if available
        if "pnf_weekly" in image_paths and image_paths["pnf_weekly"].exists():
            pnf_weekly_data = self._load_image_base64(image_paths["pnf_weekly"])
            content.append({
                "type": "text",
                "text": "POINT & FIGURE WEEKLY CHART:",
            })
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": pnf_weekly_data,
                },
            })

        # Add the analysis prompt
        content.append({
            "type": "text",
            "text": f"Stock Symbol: {symbol}\n\n{EDWARDS_MAGEE_PROMPT}",
        })

        # Send to Claude (async)
        message = await self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
        )

        response_text = message.content[0].text
        logger.debug(f"Claude response for {symbol}: {response_text[:200]}...")

        return self._parse_response(response_text, symbol)

    async def analyze_batch(
        self,
        all_image_paths: dict[str, dict[str, Path]],
        max_concurrent: int = 5,
    ) -> list[AnalysisResult]:
        """
        Analyze multiple tickers concurrently with rate limiting.

        Args:
            all_image_paths: Dict mapping symbol to its image paths dict
            max_concurrent: Maximum concurrent API requests

        Returns:
            List of AnalysisResult objects for successful analyses
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_limit(symbol: str, paths: dict[str, Path]) -> AnalysisResult:
            async with semaphore:
                return await self.analyze(paths, symbol)

        tasks = [
            analyze_with_limit(symbol, paths)
            for symbol, paths in all_image_paths.items()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and log them
        valid_results = []
        for symbol, result in zip(all_image_paths.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Analysis failed for {symbol}: {result}")
            else:
                valid_results.append(result)

        return valid_results
