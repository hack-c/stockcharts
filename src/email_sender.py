"""Gmail SMTP email sender with embedded chart images."""

import logging
import smtplib
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from .claude_analysis import AnalysisResult
from .utils import ensure_env_vars, get_project_root

logger = logging.getLogger("stockcharts")


class EmailSender:
    """Sends analysis reports via Gmail SMTP."""

    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587

    def __init__(self, config: dict):
        """
        Initialize email sender.

        Args:
            config: Email configuration dictionary
        """
        self.config = config.get("email", {})
        self.recipients = self.config.get("recipients", [])
        self.subject_prefix = self.config.get("subject_prefix", "[Stock Analysis]")

        # Load credentials
        env_vars = ensure_env_vars("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD")
        self.gmail_address = env_vars["GMAIL_ADDRESS"]
        self.gmail_password = env_vars["GMAIL_APP_PASSWORD"]

    def _get_signal_color(self, signal: str) -> str:
        """Get color for recommendation signal."""
        colors = {
            "BUY": "#28a745",   # Green
            "SELL": "#dc3545",  # Red
            "HOLD": "#ffc107",  # Yellow/Amber
        }
        return colors.get(signal.upper(), "#6c757d")

    def _get_confidence_badge(self, confidence: str) -> str:
        """Get confidence level badge HTML."""
        colors = {
            "HIGH": "#28a745",
            "MEDIUM": "#ffc107",
            "LOW": "#dc3545",
        }
        color = colors.get(confidence.upper(), "#6c757d")
        return f'<span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">{confidence}</span>'

    def _build_ticker_section(self, result: AnalysisResult, daily_cid: str, weekly_cid: str, pnf_daily_cid: str, pnf_weekly_cid: str) -> str:
        """Build HTML section for a single ticker analysis with all charts."""
        rec = result.recommendation
        signal = rec.get("signal", "HOLD")
        confidence = rec.get("confidence", "LOW")
        reasoning = rec.get("reasoning", "")

        signal_color = self._get_signal_color(signal)
        confidence_badge = self._get_confidence_badge(confidence)

        # Build patterns list
        patterns_html = ""
        if result.patterns_identified:
            patterns_list = "".join(
                f"<li>{p.get('pattern', 'Unknown')} ({p.get('implication', 'N/A')}) - {p.get('completion', 'N/A')}</li>"
                for p in result.patterns_identified
            )
            patterns_html = f"<ul style='margin: 5px 0; padding-left: 20px;'>{patterns_list}</ul>"
        else:
            patterns_html = "<p style='margin: 5px 0; color: #666;'>No significant patterns identified</p>"

        # Build observations list
        observations_html = ""
        if result.key_observations:
            obs_list = "".join(f"<li>{obs}</li>" for obs in result.key_observations)
            observations_html = f"<ul style='margin: 5px 0; padding-left: 20px;'>{obs_list}</ul>"

        # RSI info
        rsi = result.rsi
        rsi_html = ""
        if rsi:
            rsi_value = rsi.get("value", "N/A")
            rsi_zone = rsi.get("zone", "N/A")
            rsi_div = rsi.get("divergence", "NONE")
            rsi_html = f"<p style='margin: 5px 0;'><strong>RSI:</strong> {rsi_value} ({rsi_zone})"
            if rsi_div != "NONE":
                rsi_html += f" - {rsi_div} divergence"
            rsi_html += "</p>"

        # Support/Resistance
        support = ", ".join(f"${s:,.2f}" for s in result.support_levels) if result.support_levels else "N/A"
        resistance = ", ".join(f"${r:,.2f}" for r in result.resistance_levels) if result.resistance_levels else "N/A"

        chart_url = f"https://stockcharts.com/h-sc/ui?s={result.symbol}"
        pnf_url = f"https://stockcharts.com/freecharts/pnf.php?c={result.symbol},P"

        return f"""
        <div style="border: 1px solid #ddd; border-radius: 8px; margin: 20px 0; overflow: hidden;">
            <div style="background-color: {signal_color}; color: white; padding: 15px;">
                <h2 style="margin: 0; display: inline-block;">
                    <a href="{chart_url}" style="color: white; text-decoration: none;">{result.symbol}</a>
                </h2>
                <span style="float: right; font-size: 24px; font-weight: bold;">{signal}</span>
            </div>
            <div style="padding: 15px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="width: 50%; padding: 5px; vertical-align: top;">
                            <h4 style="margin: 0 0 10px 0; color: #333; font-size: 14px;">Daily</h4>
                            <img src="cid:{daily_cid}" alt="{result.symbol} Daily Chart" style="max-width: 100%; border: 1px solid #ddd; border-radius: 4px;">
                            <div style="margin-top: 5px;"><a href="{chart_url}" style="color: #3498db; text-decoration: none; font-size: 12px;">View live chart on StockCharts.com &rarr;</a></div>
                        </td>
                        <td style="width: 50%; padding: 5px; vertical-align: top;">
                            <h4 style="margin: 0 0 10px 0; color: #333; font-size: 14px;">Weekly</h4>
                            <img src="cid:{weekly_cid}" alt="{result.symbol} Weekly Chart" style="max-width: 100%; border: 1px solid #ddd; border-radius: 4px;">
                            <div style="margin-top: 5px;"><a href="{chart_url}" style="color: #3498db; text-decoration: none; font-size: 12px;">View live chart on StockCharts.com &rarr;</a></div>
                        </td>
                    </tr>
                    <tr>
                        <td style="width: 50%; padding: 5px; vertical-align: top;">
                            <h4 style="margin: 0 0 10px 0; color: #333; font-size: 14px;">P&F Daily</h4>
                            <img src="cid:{pnf_daily_cid}" alt="{result.symbol} P&F Daily" style="max-width: 100%; border: 1px solid #ddd; border-radius: 4px;">
                            <div style="margin-top: 5px;"><a href="{pnf_url}" style="color: #3498db; text-decoration: none; font-size: 12px;">View live chart on StockCharts.com &rarr;</a></div>
                        </td>
                        <td style="width: 50%; padding: 5px; vertical-align: top;">
                            <h4 style="margin: 0 0 10px 0; color: #333; font-size: 14px;">P&F Weekly</h4>
                            <img src="cid:{pnf_weekly_cid}" alt="{result.symbol} P&F Weekly" style="max-width: 100%; border: 1px solid #ddd; border-radius: 4px;">
                            <div style="margin-top: 5px;"><a href="{pnf_url}" style="color: #3498db; text-decoration: none; font-size: 12px;">View live chart on StockCharts.com &rarr;</a></div>
                        </td>
                    </tr>
                </table>

                <div style="display: flex; flex-wrap: wrap; gap: 20px;">
                    <div style="flex: 1; min-width: 250px;">
                        <h4 style="margin: 0 0 10px 0; color: #333;">Recommendation</h4>
                        <p style="margin: 5px 0;">
                            <strong>Signal:</strong> <span style="color: {signal_color}; font-weight: bold;">{signal}</span>
                            &nbsp;&nbsp;{confidence_badge}
                        </p>
                        <p style="margin: 5px 0;"><strong>Reasoning:</strong> {reasoning}</p>
                    </div>

                    <div style="flex: 1; min-width: 250px;">
                        <h4 style="margin: 0 0 10px 0; color: #333;">Trend Analysis</h4>
                        <p style="margin: 5px 0;"><strong>Primary:</strong> {result.primary_trend}</p>
                        <p style="margin: 5px 0;"><strong>Secondary:</strong> {result.secondary_trend}</p>
                        <p style="margin: 5px 0;"><strong>Volume:</strong> {result.volume_assessment}</p>
                        {rsi_html}
                    </div>
                </div>

                <div style="margin-top: 15px;">
                    <h4 style="margin: 0 0 10px 0; color: #333;">Key Levels</h4>
                    <p style="margin: 5px 0;"><strong>Support:</strong> {support}</p>
                    <p style="margin: 5px 0;"><strong>Resistance:</strong> {resistance}</p>
                </div>

                <div style="margin-top: 15px;">
                    <h4 style="margin: 0 0 10px 0; color: #333;">Patterns</h4>
                    {patterns_html}
                </div>

                <div style="margin-top: 15px;">
                    <h4 style="margin: 0 0 10px 0; color: #333;">Key Observations</h4>
                    {observations_html}
                </div>

                <div style="margin-top: 15px; padding: 10px; background-color: #f8f9fa; border-radius: 4px;">
                    <strong>Summary:</strong> {result.summary}
                </div>
            </div>
        </div>
        """

    def _build_summary_table(self, results: list[AnalysisResult]) -> str:
        """Build summary table for all tickers."""
        rows = ""
        for result in results:
            rec = result.recommendation
            signal = rec.get("signal", "HOLD")
            confidence = rec.get("confidence", "LOW")
            signal_color = self._get_signal_color(signal)

            rows += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #ddd;"><strong>{result.symbol}</strong></td>
                <td style="padding: 10px; border-bottom: 1px solid #ddd;">{result.primary_trend}</td>
                <td style="padding: 10px; border-bottom: 1px solid #ddd; color: {signal_color}; font-weight: bold;">{signal}</td>
                <td style="padding: 10px; border-bottom: 1px solid #ddd;">{confidence}</td>
            </tr>
            """

        return f"""
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <thead>
                <tr style="background-color: #f8f9fa;">
                    <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Symbol</th>
                    <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Trend</th>
                    <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Signal</th>
                    <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Confidence</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        """

    def _load_template(self) -> str:
        """Load the email template."""
        template_path = get_project_root() / "templates" / "email_template.html"
        if template_path.exists():
            with open(template_path, "r") as f:
                return f.read()

        # Default template
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 20px;">
    <h1 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
        📊 Daily Stock Analysis Report
    </h1>
    <p style="color: #666;">Generated on {{date}} using Edwards & Magee Technical Analysis methodology</p>

    <h2 style="color: #2c3e50; margin-top: 30px;">Summary</h2>
    {{summary_table}}

    <h2 style="color: #2c3e50; margin-top: 30px;">Detailed Analysis</h2>
    {{detailed_analysis}}

    <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
    <p style="color: #999; font-size: 12px;">
        This analysis is generated automatically using Claude AI based on Edwards & Magee's
        "Technical Analysis of Stock Trends" (5th Edition) methodology.
        This is not financial advice. Always do your own research before making investment decisions.
    </p>
</body>
</html>
        """

    def send_report(
        self,
        results: list[AnalysisResult],
        screenshots: dict[str, dict[str, Path]],
    ) -> None:
        """
        Send the analysis report email.

        Args:
            results: List of analysis results
            screenshots: Dict mapping symbols to {daily, weekly} screenshot paths
        """
        if not results:
            logger.warning("No results to send")
            return

        if not self.recipients:
            logger.warning("No email recipients configured")
            return

        logger.info(f"Sending report to {len(self.recipients)} recipients")

        # Create message
        msg = MIMEMultipart("related")
        msg["Subject"] = f"{self.subject_prefix} Daily Report - {datetime.now().strftime('%Y-%m-%d')}"
        msg["From"] = self.gmail_address
        msg["To"] = ", ".join(self.recipients)

        # Build HTML content
        template = self._load_template()
        summary_table = self._build_summary_table(results)

        detailed_sections = []
        image_attachments = []

        for result in results:
            symbol = result.symbol
            daily_cid = f"chart_{symbol}_daily"
            weekly_cid = f"chart_{symbol}_weekly"
            pnf_daily_cid = f"chart_{symbol}_pnf_daily"
            pnf_weekly_cid = f"chart_{symbol}_pnf_weekly"

            # Add detailed section
            detailed_sections.append(self._build_ticker_section(result, daily_cid, weekly_cid, pnf_daily_cid, pnf_weekly_cid))

            # Prepare image attachments
            if symbol in screenshots:
                chart_paths = screenshots[symbol]

                # Daily chart
                if "daily" in chart_paths and chart_paths["daily"].exists():
                    with open(chart_paths["daily"], "rb") as f:
                        img_data = f.read()
                    img = MIMEImage(img_data)
                    img.add_header("Content-ID", f"<{daily_cid}>")
                    img.add_header("Content-Disposition", "inline", filename=f"{symbol}_daily.png")
                    image_attachments.append(img)

                # Weekly chart
                if "weekly" in chart_paths and chart_paths["weekly"].exists():
                    with open(chart_paths["weekly"], "rb") as f:
                        img_data = f.read()
                    img = MIMEImage(img_data)
                    img.add_header("Content-ID", f"<{weekly_cid}>")
                    img.add_header("Content-Disposition", "inline", filename=f"{symbol}_weekly.png")
                    image_attachments.append(img)

                # P&F Daily chart
                if "pnf_daily" in chart_paths and chart_paths["pnf_daily"].exists():
                    with open(chart_paths["pnf_daily"], "rb") as f:
                        img_data = f.read()
                    img = MIMEImage(img_data)
                    img.add_header("Content-ID", f"<{pnf_daily_cid}>")
                    img.add_header("Content-Disposition", "inline", filename=f"{symbol}_pnf_daily.png")
                    image_attachments.append(img)

                # P&F Weekly chart
                if "pnf_weekly" in chart_paths and chart_paths["pnf_weekly"].exists():
                    with open(chart_paths["pnf_weekly"], "rb") as f:
                        img_data = f.read()
                    img = MIMEImage(img_data)
                    img.add_header("Content-ID", f"<{pnf_weekly_cid}>")
                    img.add_header("Content-Disposition", "inline", filename=f"{symbol}_pnf_weekly.png")
                    image_attachments.append(img)

        # Replace placeholders in template
        html_content = template.replace("{{date}}", datetime.now().strftime("%B %d, %Y at %I:%M %p"))
        html_content = html_content.replace("{{summary_table}}", summary_table)
        html_content = html_content.replace("{{detailed_analysis}}", "\n".join(detailed_sections))

        # Attach HTML
        msg_alternative = MIMEMultipart("alternative")
        msg_alternative.attach(MIMEText(html_content, "html"))
        msg.attach(msg_alternative)

        # Attach images
        for img in image_attachments:
            msg.attach(img)

        # Send email
        try:
            with smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT) as server:
                server.starttls()
                server.login(self.gmail_address, self.gmail_password)
                server.sendmail(self.gmail_address, self.recipients, msg.as_string())

            logger.info("Report email sent successfully")

        except smtplib.SMTPAuthenticationError:
            logger.error(
                "Gmail authentication failed. Make sure you're using an App Password "
                "(not your regular password) and have 2FA enabled."
            )
            raise
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise
