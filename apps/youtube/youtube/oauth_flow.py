import httpx

from core.vault import SqlVault


def exchange_code(client_id: str, client_secret: str, redirect_uri: str, code: str) -> dict:
    response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def store_tokens(vault: SqlVault, payload: dict) -> None:
    if "refresh_token" in payload:
        vault.put("youtube_refresh_token", payload["refresh_token"])
    if "access_token" in payload:
        vault.put("youtube_access_token", payload["access_token"])
