# -*- coding: utf-8 -*-
"""GitHub Actions üzerinden zamanlanmış BIST taraması + Telegram bildirimi.

Tarama çekirdeğine dokunmaz; mevcut scan_worker._scan_chunk fonksiyonunu kullanır.
Saatler auto_scan_settings.json veya GitHub Actions Variables üzerinden değiştirilebilir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from scan_worker import _scan_chunk
from telegram_notifier import TelegramNotifier, esc
from vwap_core import normalize_symbol_list

BASE_DIR = Path(__file__).resolve().parent
AUTO_SETTINGS = BASE_DIR / "auto_scan_settings.json"
APP_SETTINGS = BASE_DIR / ".vwap_ayarlar.json"
BIST_LIST = BASE_DIR / "bist_list.txt"
STATE_PATH = BASE_DIR / ".auto_scan_state.json"

PHASES = ["VWAP", "Üçgen", "Düşen Trend", "Alternasyon"]


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "evet", "açık", "acik"}


def load_auto_settings() -> dict:
    cfg = _read_json(AUTO_SETTINGS, {})
    if os.getenv("SCAN_TIMES", "").strip():
        cfg["times"] = [x.strip() for x in os.getenv("SCAN_TIMES", "").split(",") if x.strip()]
    if os.getenv("AUTO_SCAN_ENABLED", "").strip():
        cfg["enabled"] = _env_bool("AUTO_SCAN_ENABLED", bool(cfg.get("enabled", True)))
    if os.getenv("AUTO_MIN_SCORE", "").strip():
        cfg["min_score"] = float(os.getenv("AUTO_MIN_SCORE"))
    if os.getenv("AUTO_MIN_SIGNALS", "").strip():
        cfg["min_signal_count"] = int(os.getenv("AUTO_MIN_SIGNALS"))
    if os.getenv("AUTO_SCAN_MODE", "").strip():
        cfg["scan_mode"] = os.getenv("AUTO_SCAN_MODE").strip()
    if os.getenv("APP_URL", "").strip():
        cfg["app_url"] = os.getenv("APP_URL").strip()
    return cfg


def load_app_settings() -> dict:
    return _read_json(APP_SETTINGS, {})


def load_symbols(app_cfg: dict):
    text = str(app_cfg.get("son_semboller_text") or "").strip()
    if not text:
        try:
            text = BIST_LIST.read_text(encoding="utf-8-sig")
        except Exception:
            text = ""
    return normalize_symbol_list([text])


def load_state() -> dict:
    state = _read_json(STATE_PATH, {})
    state.setdefault("executed_slots", {})
    state.setdefault("sent_fingerprints", {})
    return state


def save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def cleanup_state(state: dict, now: datetime, dedupe_days: int):
    cutoff = now - timedelta(days=max(1, int(dedupe_days)))
    sent = {}
    for fp, ts in (state.get("sent_fingerprints") or {}).items():
        try:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=now.tzinfo)
            if dt >= cutoff:
                sent[fp] = ts
        except Exception:
            pass
    state["sent_fingerprints"] = sent
    slot_cutoff = now - timedelta(days=7)
    slots = {}
    for key, ts in (state.get("executed_slots") or {}).items():
        try:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=now.tzinfo)
            if dt >= slot_cutoff:
                slots[key] = ts
        except Exception:
            pass
    state["executed_slots"] = slots


def find_due_slot(cfg: dict, state: dict, now: datetime):
    if not bool(cfg.get("enabled", True)):
        return None
    weekdays = {int(x) for x in cfg.get("weekdays", [0, 1, 2, 3, 4])}
    if now.weekday() not in weekdays:
        return None
    grace = max(0, int(cfg.get("grace_minutes", 9)))
    candidates = []
    for raw in cfg.get("times", []):
        try:
            hh, mm = [int(x) for x in str(raw).split(":", 1)]
            slot_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            delta = (now - slot_dt).total_seconds() / 60.0
            if 0 <= delta <= grace:
                key = f"{slot_dt.date().isoformat()}_{hh:02d}{mm:02d}"
                if key not in (state.get("executed_slots") or {}):
                    candidates.append((delta, key, slot_dt))
        except Exception:
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1], candidates[0][2]


def q_score(row) -> float:
    try:
        return float(((row or {}).get("quality") or {}).get("score") or 0.0)
    except Exception:
        return 0.0


def _sym(row):
    return str((row or {}).get("symbol") or "").replace(".IS", "").upper()


def run_all_scans(symbols, app_cfg: dict, scan_mode: str):
    if scan_mode in PHASES:
        phases = [scan_mode]
    else:
        phases = PHASES
    results = {}
    errors = {}
    total = len(symbols)
    for phase in phases:
        phase_errors = []
        print(f"[{phase}] {total} hisse taranıyor...", flush=True)
        out = _scan_chunk(phase, symbols, app_cfg, None, phase_errors)
        results[phase] = list((out or {}).get("rows") or [])
        errors[phase] = phase_errors
        print(f"[{phase}] {len(results[phase])} sonuç, {len(phase_errors)} hata", flush=True)
    return results, errors


def combine(results: dict):
    by_sym = {}
    for phase, rows in results.items():
        for row in rows or []:
            sym = _sym(row)
            if not sym:
                continue
            by_sym.setdefault(sym, {})[phase] = row
    out = []
    for sym, signals in by_sym.items():
        scores = [(q_score(r), name, r) for name, r in signals.items()]
        scores.sort(key=lambda x: x[0], reverse=True)
        best_score, best_name, best = scores[0]
        q = (best or {}).get("quality") or {}
        out.append({
            "symbol": sym,
            "signals": signals,
            "signal_count": len(signals),
            "best_score": round(best_score, 1),
            "avg_score": round(sum(s[0] for s in scores) / len(scores), 1),
            "best_name": best_name,
            "quality": q,
            "last_close": best.get("last_close") if isinstance(best, dict) else None,
        })
    out.sort(key=lambda x: (x["signal_count"], x["best_score"], x["avg_score"]), reverse=True)
    return out


def fingerprint(candidate: dict) -> str:
    parts = [candidate.get("symbol", "")]
    for name in PHASES:
        r = (candidate.get("signals") or {}).get(name)
        if not r:
            continue
        if name == "VWAP":
            parts.append(f"VWAP:{r.get('level')}:{r.get('cross_date')}:{r.get('cross_idx')}")
        elif name == "Üçgen":
            parts.append(f"TRI:{r.get('pattern_type')}:{r.get('apex_x')}:{r.get('end_date')}")
        elif name == "Düşen Trend":
            parts.append(f"TL:{r.get('cross_date')}:{r.get('cross_idx')}:{r.get('touches')}")
        elif name == "Alternasyon":
            parts.append(f"ALT:{r.get('start_date')}:{r.get('end_date')}:{r.get('chain_length')}")
    raw = "|".join(str(x) for x in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _pct(v):
    try:
        return f"%{float(v):.1f}"
    except Exception:
        return "—"


def _num(v, digits=1):
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return "—"


def build_message(c: dict, cfg: dict) -> str:
    signals = c.get("signals") or {}
    fire = "🔥🔥" if c.get("signal_count", 0) >= int(cfg.get("priority_signal_count", 2)) else "📈"
    lines = [
        f"{fire} <b>{esc(c.get('symbol'))}</b>",
        f"<b>{c.get('signal_count')} teknik sinyal</b> · Max puan <b>{_num(c.get('best_score'))}/100</b> · Ort. {_num(c.get('avg_score'))}",
    ]
    if c.get("last_close") is not None:
        lines.append(f"Fiyat: <b>{_num(c.get('last_close'), 2)}</b>")

    v = signals.get("VWAP")
    if v:
        dd = (v.get("drawdown") or {}).get("drawdown_pct")
        sw = v.get("sideways") or {}
        sw_txt = "✅" if sw.get("is_sideways") else "❌"
        lines.append(f"📍 VWAP: <b>{esc(v.get('level', '—'))}. VWAP</b> · {esc(v.get('cross_date', '—'))} · {esc(v.get('bars_ago', '—'))} bar önce")
        lines.append(f"   Yataylık {sw_txt} · Düşüş {_pct(dd)}")

    t = signals.get("Üçgen")
    if t:
        lines.append(f"🔺 Üçgen: <b>{esc(t.get('pattern_type') or 'Evet')}</b> · sıkışma {_pct(t.get('squeeze_pct'))}")

    tr = signals.get("Düşen Trend")
    if tr:
        lines.append(f"📉 Düşen trend: <b>Kırılım</b> · {esc(tr.get('touches', '—'))} temas · {esc(tr.get('cross_date', '—'))}")

    a = signals.get("Alternasyon")
    if a:
        lines.append(f"🔀 Alternasyon: <b>{esc(a.get('chain_length', '—'))} mum</b> · desen {_num(a.get('score'))}/100")

    q = c.get("quality") or {}
    qparts = []
    if q.get("rsi14") is not None:
        qparts.append(f"RSI {_num(q.get('rsi14'))}")
    if q.get("volume_ratio") is not None:
        qparts.append(f"Hacim {_num(q.get('volume_ratio'), 2)}x")
    if q.get("resistance_room_pct") is not None:
        qparts.append(f"Direnç alan {_pct(q.get('resistance_room_pct'))}")
    if qparts:
        lines.append("⚙️ " + " · ".join(qparts))
    reasons = q.get("reasons") or []
    if reasons:
        lines.append("✅ " + esc(" · ".join(reasons[:3])))
    app_url = str(cfg.get("app_url") or "").strip()
    if app_url:
        lines.append(f'<a href="{esc(app_url)}">Uygulamayı aç</a>')
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--scheduled", action="store_true")
    group.add_argument("--force", action="store_true")
    args = parser.parse_args()

    auto_cfg = load_auto_settings()
    tz = ZoneInfo(str(auto_cfg.get("timezone") or "Europe/Istanbul"))
    now = datetime.now(tz)
    state = load_state()
    cleanup_state(state, now, int(auto_cfg.get("dedupe_days", 14)))

    slot_key = None
    if not args.force:
        due = find_due_slot(auto_cfg, state, now)
        if not due:
            print(f"Tarama saati değil: {now.strftime('%d.%m.%Y %H:%M %Z')}")
            save_state(state)
            return 0
        slot_key, slot_dt = due
        print(f"Tarama slotu: {slot_dt.strftime('%d.%m.%Y %H:%M')}")
    else:
        print("Manuel/force tarama başlatılıyor.")

    app_cfg = load_app_settings()
    symbols = load_symbols(app_cfg)
    if not symbols:
        raise RuntimeError("Taranacak hisse listesi boş.")

    scan_mode = str(auto_cfg.get("scan_mode") or "Tümünü Tara")
    results, errors = run_all_scans(symbols, app_cfg, scan_mode)
    candidates = combine(results)
    min_score = float(auto_cfg.get("min_score", 70))
    min_signals = int(auto_cfg.get("min_signal_count", 1))
    candidates = [c for c in candidates if c["best_score"] >= min_score and c["signal_count"] >= min_signals]

    new_candidates = []
    for c in candidates:
        fp = fingerprint(c)
        c["fingerprint"] = fp
        if fp not in state.get("sent_fingerprints", {}):
            new_candidates.append(c)

    max_messages = max(1, int(auto_cfg.get("max_messages_per_run", 20)))
    new_candidates = new_candidates[:max_messages]
    notifier = TelegramNotifier()

    if new_candidates:
        header = (
            f"🤖 <b>BIST Otomatik Tarama</b>\n"
            f"{esc(now.strftime('%d.%m.%Y %H:%M'))} · {len(symbols)} hisse\n"
            f"Yeni bildirim: <b>{len(new_candidates)}</b> · Aday toplamı: {len(candidates)}"
        )
        notifier.send(header)
        for c in new_candidates:
            notifier.send(build_message(c, auto_cfg))
            state["sent_fingerprints"][c["fingerprint"]] = now.isoformat()
    elif bool(auto_cfg.get("send_summary_when_empty", False)):
        notifier.send(
            f"🤖 <b>BIST Otomatik Tarama</b>\n{esc(now.strftime('%d.%m.%Y %H:%M'))}\nYeni sinyal yok."
        )

    if slot_key:
        state["executed_slots"][slot_key] = now.isoformat()
    state["last_run"] = {
        "time": now.isoformat(),
        "symbols": len(symbols),
        "candidates": len(candidates),
        "new_sent": len(new_candidates),
        "scan_mode": scan_mode,
        "errors": {k: len(v or []) for k, v in errors.items()},
    }
    save_state(state)
    print(f"Tamamlandı. Aday: {len(candidates)}, yeni Telegram: {len(new_candidates)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"AUTO_SCAN_ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
