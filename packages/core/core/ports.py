"""Ports for the two engines. Adapters live in apps/*/providers. Swap memory → live without touching workflows."""

from __future__ import annotations

from typing import Protocol


class EmailSender(Protocol):
    def send(self, request: dict) -> dict: ...


class EmailVerifier(Protocol):
    def verify(self, email: str) -> str: ...


class CalendarPort(Protocol):
    def book(self, email: str, slot: str) -> dict: ...


class PaymentsPort(Protocol):
    def create_link(self, amount_cents: int, currency: str, metadata: dict) -> dict: ...


class ESignPort(Protocol):
    def send(self, **kwargs) -> dict: ...


class VideoClient(Protocol):
    def upload(self, request: dict) -> dict: ...


class ObjectStore(Protocol):
    def put(self, key: str, body: bytes, content_type: str = "application/octet-stream") -> str: ...


class CachePort(Protocol):
    def get(self, key: str) -> int: ...
    def set(self, key: str, value: int) -> None: ...
    def incr(self, key: str, amount: int = 1) -> int: ...
