# -*- coding: utf-8 -*-
"""GitHub Actions repository variable üzerinden otomatik tarama ayarlarını yönetir.

Gizli token hiçbir zaman GitHub değişkenine yazılmaz. Streamlit Secrets içinde tutulur.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

import requests

GITHUB_API = "https://api.github.com"
DEFAULT_OWNER = "suleymanozer87-dot"
DEFAULT_REPO = "bist-tarama"
VARIABLE_NAME = "AUTO_SCAN_CONFIG_JSON"
API_VERSION = "2026-03-10"


def _headers(token: str) -> Dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "bist-tarama-streamlit-settings",
    }


def _url(owner: str, repo: str, name: Optional[str] = None) -> str:
    base = f"{GITHUB_API}/repos/{owner}/{repo}/actions/variables"
    return f"{base}/{name}" if name else base


def get_repo_variable(token: str, *, owner: str = DEFAULT_OWNER, repo: str = DEFAULT_REPO,
                      name: str = VARIABLE_NAME, timeout: int = 12) -> Tuple[Optional[str], Optional[str]]:
    if not token:
        return None, "GitHub token tanımlı değil."
    try:
        r = requests.get(_url(owner, repo, name), headers=_headers(token), timeout=timeout)
        if r.status_code == 404:
            return None, None
        if r.status_code != 200:
            return None, f"GitHub API {r.status_code}: {r.text[:220]}"
        data = r.json()
        return str(data.get("value") or ""), None
    except Exception as exc:
        return None, f"GitHub bağlantısı kurulamadı: {type(exc).__name__}: {exc}"


def upsert_repo_variable(token: str, value: str, *, owner: str = DEFAULT_OWNER, repo: str = DEFAULT_REPO,
                         name: str = VARIABLE_NAME, timeout: int = 12) -> Tuple[bool, Optional[str]]:
    if not token:
        return False, "GitHub token tanımlı değil."
    headers = _headers(token)
    try:
        existing, err = get_repo_variable(token, owner=owner, repo=repo, name=name, timeout=timeout)
        if err:
            return False, err
        if existing is None:
            r = requests.post(_url(owner, repo), headers=headers, json={"name": name, "value": value}, timeout=timeout)
            if r.status_code != 201:
                return False, f"GitHub variable oluşturulamadı ({r.status_code}): {r.text[:220]}"
            return True, None
        r = requests.patch(_url(owner, repo, name), headers=headers, json={"name": name, "value": value}, timeout=timeout)
        if r.status_code != 204:
            return False, f"GitHub variable güncellenemedi ({r.status_code}): {r.text[:220]}"
        return True, None
    except Exception as exc:
        return False, f"GitHub bağlantısı kurulamadı: {type(exc).__name__}: {exc}"


def encode_config(cfg: Dict[str, Any]) -> str:
    return json.dumps(cfg or {}, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def decode_config(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}
