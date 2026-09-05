# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import os
import time
from typing import Iterable, Optional

import requests


class TelegramNotifier:
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None, timeout: int = 20):
        self.token = (token or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        self.chat_id = (chat_id or os.getenv("TELEGRAM_CHAT_ID") or "").strip()
        self.timeout = int(timeout)
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN tanımlı değil.")
        if not self.chat_id:
            raise RuntimeError("TELEGRAM_CHAT_ID tanımlı değil.")

    @property
    def endpoint(self) -> str:
        return f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send(self, text: str, *, disable_preview: bool = True) -> dict:
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": bool(disable_preview),
        }
        resp = requests.post(self.endpoint, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API hatası: {data}")
        return data

    def send_many(self, messages: Iterable[str], *, delay_seconds: float = 0.35) -> int:
        sent = 0
        for msg in messages:
            self.send(msg)
            sent += 1
            if delay_seconds:
                time.sleep(delay_seconds)
        return sent


def esc(value) -> str:
    return html.escape(str(value if value is not None else "—"), quote=False)
