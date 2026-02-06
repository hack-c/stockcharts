# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated stock chart analysis workflow that:
1. Captures charts from StockCharts.com using Playwright (daily/weekly candlestick + P&F charts)
2. Analyzes them with Claude API using Edwards & Magee "Technical Analysis of Stock Trends" 5th Edition methodology
3. Sends HTML email reports via Gmail SMTP with embedded charts

## Common Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Run full workflow (all tickers, with email)
python -m src.main

# Test single ticker without email
python -m src.main -t AAPL --no-email

# Test multiple tickers without email
python -m src.main -t AAPL NVDA GOOG --no-email

# Debug with visible browser
python -m src.main --ticker AAPL --no-headless --no-email

# Capture charts only (skip Claude analysis and email)
python -m src.main --dry-run

# Verbose logging
python -m src.main --verbose
```

## Architecture

### Data Flow
`main.py` → `BrowserManager` → `ChartCapture` → `ClaudeAnalyzer` → `EmailSender`

### Key Components

- **`src/main.py`**: Orchestrator - loads config, iterates tickers, coordinates capture→analyze→email pipeline
- **`src/browser.py`**: `BrowserManager` class - Playwright lifecycle management with context managers
- **`src/chart_capture.py`**: `ChartCapture` class - StockCharts.com automation, captures 4 chart types per ticker (daily, weekly, P&F daily, P&F weekly)
- **`src/claude_analysis.py`**: `ClaudeAnalyzer` class - sends chart images to Claude API with Edwards & Magee analysis prompt, returns structured `AnalysisResult`
- **`src/email_sender.py`**: `EmailSender` class - builds HTML email with embedded charts (CID references), sends via Gmail SMTP
- **`src/utils.py`**: Shared utilities - config loading, logging setup, `@retry` decorator, env var validation

### Configuration Files
- `config/config.yaml` - chart settings, browser config, email recipients, Claude model
- `config/tickers.yaml` - stock watchlist (symbol + name)
- `config/.env` - secrets: `ANTHROPIC_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`

### StockCharts.com Selectors
Key element IDs used in `chart_capture.py`:
- `#chart-type-menu-lower` - chart type select
- `#period-dropdown-menu-toggle-button` - period dropdown (Daily/Weekly)
- `#range-dropdown-menu-toggle-button` - range dropdown (1 Year, 5 Years, etc.)
- `#indicator-menu-1` - indicator select (RSI)
- `#chart-image` - the chart image element
- `#SCForm1-period` - P&F chart period select
- `#submitButton` - P&F Update button

Weekly candlestick charts use "5 Years" range; daily charts use default "1 Year".

### Playwright Notes
- Use `:text-is("...")` for exact text matching in dropdowns (not `:has-text()` which does partial matching)
- P&F page requires clicking Update button after changing period dropdown
- Wait for `#chart-image` src to change after settings changes to confirm chart updated
