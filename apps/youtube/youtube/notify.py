from core.errors import MissingCredentials


class Notifier:
    def __init__(self):
        self.sent: list[dict] = []

    def send(self, message: str, channel: str = "email") -> dict:
        row = {"channel": channel, "message": message}
        self.sent.append(row)
        return row


class EmailNotifier:
    def __init__(self, to_address: str):
        if not to_address:
            raise MissingCredentials("ALERT_EMAIL_TO")
        self.to_address = to_address
        self.sent: list[dict] = []

    def send(self, message: str, channel: str = "email") -> dict:
        row = {"channel": "email", "to": self.to_address, "message": message}
        self.sent.append(row)
        return row


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        if not bot_token or not chat_id:
            raise MissingCredentials("Telegram alerts")
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, message: str, channel: str = "telegram") -> dict:
        import httpx

        response = httpx.post(
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            json={"chat_id": self.chat_id, "text": message},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
