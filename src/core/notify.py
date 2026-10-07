from core.config import get_settings


class NotifierHub:
    def __init__(self):
        self.sent: list[dict] = []
        self.settings = get_settings()

    def default_channels(self) -> list[str]:
        raw = self.settings.owner_notify_channels or "log"
        return [item.strip() for item in raw.split(",") if item.strip()]

    def alert(self, message: str, channels: list[str] | None = None) -> list[dict]:
        channels = channels or self.default_channels()
        results = []
        for channel in channels:
            if channel == "email" and self.settings.alert_email_to:
                results.append(self._send_email(message))
            elif channel == "slack" and self.settings.slack_webhook_url:
                results.append(self._send_slack(message))
            elif channel == "telegram" and self.settings.telegram_bot_token and self.settings.telegram_chat_id:
                results.append(self._send_telegram(message))
            else:
                results.append({"channel": channel or "log", "message": message})
            self.sent.append(results[-1])
        return results

    def _send_slack(self, message: str) -> dict:
        try:
            import httpx

            response = httpx.post(
                self.settings.slack_webhook_url,
                json={"text": message},
                timeout=20,
            )
            response.raise_for_status()
            return {"channel": "slack", "message": message, "status": response.status_code}
        except Exception as exc:
            return {"channel": "slack", "error": str(exc), "message": message}

    def _send_telegram(self, message: str) -> dict:
        try:
            import httpx

            httpx.post(
                f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage",
                json={"chat_id": self.settings.telegram_chat_id, "text": message},
                timeout=20,
            )
            return {"channel": "telegram", "message": message}
        except Exception as exc:
            return {"channel": "telegram", "error": str(exc)}

    def _send_email(self, message: str) -> dict:
        """Log structured email alert; wire SMTP or a transactional provider when configured."""
        return {"channel": "email", "to": self.settings.alert_email_to, "message": message, "queued": True}
