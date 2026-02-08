# Daily Stock Chart Analysis Workflow

Automated Python workflow that captures stock charts from StockCharts.com, analyzes them using Claude AI with **Edwards & Magee's *Technical Analysis of Stock Trends* (5th Edition)** methodology, and emails the results with buy/sell alerts.

## Features

- **Automated chart capture** from StockCharts.com (daily/weekly candlestick + Point & Figure)
- **AI-powered analysis** using Claude with Edwards & Magee methodology
- **Parallel processing** - multiple tickers and chart types captured concurrently
- **HTML email reports** with embedded charts and color-coded BUY/SELL/HOLD signals
- **Scheduled execution** via macOS launchd (runs daily at 6:30 AM)
- **Configurable** ticker watchlist and analysis parameters

## Prerequisites

- Python 3.11+
- macOS (for launchd scheduling)
- Gmail account with 2FA and App Password
- Anthropic API key

## Quick Start

### 1. Clone and Setup

```bash
cd /Users/charlie/Documents/projects/stockcharts

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Configure Credentials

```bash
# Copy the example env file
cp config/.env.example config/.env

# Edit with your credentials
nano config/.env
```

Add your credentials:
```
ANTHROPIC_API_KEY=your-anthropic-api-key
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password
```

**Gmail App Password Setup:**
1. Enable 2FA on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Generate a new app password for "Mail"

### 3. Configure Tickers

Edit `config/tickers.yaml` to customize your watchlist:

```yaml
tickers:
  - symbol: "AAPL"
    name: "Apple Inc."
  - symbol: "MSFT"
    name: "Microsoft Corporation"
  # Add more...
```

### 4. Run Analysis

```bash
# Activate virtual environment
source .venv/bin/activate

# Run full workflow
python -m src.main

# Test with single ticker (no email)
python -m src.main --ticker AAPL --no-email

# Debug mode (visible browser)
python -m src.main --ticker AAPL --no-headless --no-email

# Dry run (capture charts only)
python -m src.main --dry-run
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `--ticker`, `-t` | Analyze specific ticker(s) instead of configured list |
| `--no-email` | Skip sending email report |
| `--no-headless` | Show browser window (for debugging) |
| `--dry-run` | Capture charts only, skip analysis and email |
| `--max-concurrent N` | Max parallel tickers (default: 3) |
| `--verbose`, `-v` | Enable debug logging |

## Scheduling with launchd

### Install the Launch Agent

```bash
# Copy plist to LaunchAgents
cp launchd/com.stockcharts.daily-analysis.plist ~/Library/LaunchAgents/

# Load the agent
launchctl load ~/Library/LaunchAgents/com.stockcharts.daily-analysis.plist

# Verify it's loaded
launchctl list | grep stockcharts
```

### Manage the Schedule

```bash
# Unload (disable)
launchctl unload ~/Library/LaunchAgents/com.stockcharts.daily-analysis.plist

# Manually trigger
launchctl start com.stockcharts.daily-analysis

# View logs
tail -f logs/launchd-stdout.log
tail -f logs/launchd-stderr.log
```

### Change Schedule Time

Edit the plist file and modify:
```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>6</integer>  <!-- 6 AM -->
    <key>Minute</key>
    <integer>30</integer> <!-- :30 -->
</dict>
```

Then reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.stockcharts.daily-analysis.plist
launchctl load ~/Library/LaunchAgents/com.stockcharts.daily-analysis.plist
```

## Project Structure

```
stockcharts/
├── config/
│   ├── config.yaml         # Chart settings, email config
│   ├── tickers.yaml        # Stock watchlist
│   └── .env                # Secrets (API keys, passwords)
├── src/
│   ├── main.py             # Async orchestrator with parallel processing
│   ├── browser.py          # AsyncBrowserManager (Playwright lifecycle)
│   ├── chart_capture.py    # StockCharts automation & screenshots
│   ├── claude_analysis.py  # Claude API with batch analysis
│   ├── email_sender.py     # Gmail SMTP with embedded images
│   └── utils.py            # Config loading, logging, retry decorators
├── templates/
│   └── email_template.html # HTML email template
├── output/screenshots/     # Captured chart images
├── logs/                   # Application logs
├── launchd/
│   └── com.stockcharts.daily-analysis.plist
├── requirements.txt
└── README.md
```

## Architecture

The workflow uses async/await throughout for parallel processing:

```
main.py (asyncio.run)
├── Parallel ticker capture (up to 3 concurrent by default)
│   └── Per ticker: candlestick + P&F charts in parallel browser contexts
├── Batch Claude API calls (up to 5 concurrent)
└── Single email with all results
```

**Performance**: 10 tickers complete in ~1-2 minutes vs ~5+ minutes sequential.

## Edwards & Magee Analysis

The analysis follows the classical technical analysis methodology from the 5th Edition:

1. **Trend Analysis** - Primary, secondary, and minor trends per Dow Theory
2. **Chart Patterns** - Classical reversal and continuation patterns
3. **Support/Resistance** - Key price levels from historical data
4. **Volume** - Confirmation of price movements (emphasized in 5th ed.)
5. **RSI** - Modern overlay for overbought/oversold conditions
6. **Recommendation** - BUY/SELL/HOLD with confidence level

## Configuration

### config/config.yaml

```yaml
chart:
  type: "candlestick"
  period: "9 months"
  indicators:
    - name: "RSI"
      period: 14

browser:
  headless: true
  timeout: 30000
  viewport:
    width: 1920
    height: 1080

email:
  recipients:
    - "your-email@gmail.com"
  subject_prefix: "[Stock Analysis]"

analysis:
  model: "claude-sonnet-4-20250514"
  max_tokens: 2000
```

## Estimated Costs

- Claude API: ~$0.003-0.01 per chart analysis
- 10 tickers daily ≈ $0.03-0.10/day ≈ $1-3/month

## Troubleshooting

### Browser Issues
```bash
# Reinstall Playwright browsers
playwright install chromium --force
```

### Email Authentication Failed
- Ensure 2FA is enabled on Gmail
- Use App Password, not regular password
- Check for typos in credentials

### Chart Not Loading
- Run with `--no-headless` to see what's happening
- Check if StockCharts.com site has changed
- Increase timeout in config.yaml

### launchd Not Running
- Mac must be awake at scheduled time (or job runs when it wakes)
- Check logs in `logs/launchd-*.log`
- Verify plist is loaded: `launchctl list | grep stockcharts`

## License

MIT License
