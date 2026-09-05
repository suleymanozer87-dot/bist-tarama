# -*- coding: utf-8 -*-
"""BIST VWAP Tarayıcı — sade, mobil uyumlu Streamlit arayüzü."""

import ast
import json
import os
import sys
import html
import copy
from datetime import datetime

import pandas as pd
import streamlit as st

from vwap_core import (
    ALTERNATION_MIN_CHAIN,
    ALTERNATION_SCAN_PERIOD_LABELS,
    ALTERNATION_SCAN_PERIOD_OPTIONS,
    CURRENCY_OPTIONS,
    DEFAULT_SYMBOLS,
    PERIOD_LABELS,
    PERIOD_OPTIONS,
    TRENDLINE_LOOKBACK_BARS,
    TRENDLINE_MIN_SPAN_BARS,
    TRENDLINE_MIN_TOUCHES,
    TRENDLINE_PIVOT_WINDOW,
    TRENDLINE_SCAN_PERIOD_LABELS,
    TRENDLINE_SCAN_PERIOD_OPTIONS,
    TRENDLINE_TOUCH_TOLERANCE_PCT,
    TRENDLINE_VOLUME_FACTOR,
    TRIANGLE_LOOKBACK_BARS,
    TRIANGLE_MAX_APEX_BARS_AHEAD,
    TRIANGLE_MAX_SQUEEZE_PCT,
    TRIANGLE_MIN_APEX_BARS_AHEAD,
    TRIANGLE_MIN_SPAN_BARS,
    TRIANGLE_PIVOT_WINDOW,
    TRIANGLE_SCAN_PERIOD_LABELS,
    TRIANGLE_SCAN_PERIOD_OPTIONS,
    fetch_and_scan_alternation_only,
    fetch_and_scan_trendline_only,
    fetch_and_scan_triangle_only,
    normalize_symbol_list,
    scan_alternation_symbols_parallel,
    scan_symbols_parallel,
    scan_trendline_symbols_parallel,
    scan_triangle_symbols_parallel,
)
from chart_helpers import (
    render_alternation_chart,
    render_combined_chart,
    render_triangle_chart,
    render_trendline_chart,
    render_vwap_chart,
)
from scan_jobs import get_scan_job_manager
from github_auto_settings import (
    DEFAULT_OWNER as GITHUB_DEFAULT_OWNER,
    DEFAULT_REPO as GITHUB_DEFAULT_REPO,
    VARIABLE_NAME as AUTO_CONFIG_VARIABLE,
    decode_config as decode_auto_config,
    encode_config as encode_auto_config,
    get_repo_variable as github_get_repo_variable,
    upsert_repo_variable as github_upsert_repo_variable,
)

# Yukarıdaki koşullu import ifadesi yalnız eski sabit adıyla uyumluluk için yazılmıştır;
# Python import listesinde koşul kullanılamaz. Bu satır dosya oluşturulurken aşağıda temizlenir.

st.set_page_config(
    page_title="BIST Teknik Tarayıcı",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------------------------------------------------------
# Görünüm — tek açık tema, mobilde tüm sütunlar otomatik alt alta.
# -----------------------------------------------------------------------------
st.markdown(
    """
<style>
:root { color-scheme: light; }
[data-testid="stAppViewContainer"] { background: #f2f2f7; color: #111827; }
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] { display:none !important; }
.block-container { max-width: 980px; padding-top: 1rem; padding-bottom: 1.5rem; }
h1, h2, h3 { color:#111827; letter-spacing:-.02em; margin-bottom:.35rem; }
p, .small-muted, [data-testid="stCaptionContainer"] { color:#6b7280; }
.hero {
    background:#ffffff; border:1px solid #e5e7eb; border-radius:22px; padding:18px;
    box-shadow:0 10px 28px rgba(17,24,39,.05); margin-bottom:14px;
}
.scan-card, .result-card, [data-testid="stMetric"], [data-testid="stExpander"] {
    background:#ffffff; border:1px solid #e5e7eb !important; border-radius:20px !important;
    box-shadow:0 6px 20px rgba(17,24,39,.04);
}
.scan-card { padding:14px 16px; min-height:88px; }
.result-card { padding:10px 12px; margin-bottom:8px; }
[data-testid="stMetric"] { padding:.7rem .85rem; }
.stButton > button, .stDownloadButton > button {
    border-radius:16px; min-height:2.8rem; font-weight:700; border:1px solid #d1d5db;
}
button[kind="primary"] {
    background:#0a84ff !important; border-color:#0a84ff !important; color:white !important;
    box-shadow:0 8px 18px rgba(10,132,255,.18);
}
button[kind="secondary"] {
    background:#ffffff !important; color:#111827 !important;
}
[data-testid="stDataFrame"] { background:#ffffff; border:1px solid #e5e7eb; border-radius:20px; overflow:hidden; }
.nav-shell {
    background:#ffffff; border:1px solid #e5e7eb; border-radius:20px; padding:10px; margin:0 0 12px 0;
    box-shadow:0 8px 22px rgba(17,24,39,.04);
}
.nav-label { color:#9ca3af; font-size:.72rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; margin:0 0 6px 4px; }
.nav-spacer { height:2px; }
.compact-status {
    background:#ffffff; border:1px solid #e5e7eb; border-radius:18px; padding:12px 14px; margin-bottom:12px;
    box-shadow:0 6px 20px rgba(17,24,39,.04);
}
.compact-status strong { color:#111827; }
hr { border-color:#e5e7eb !important; }

/* Segmented controls */
div[role="radiogroup"] { gap:.35rem !important; }
div[role="radiogroup"] label {
    background:#ffffff !important; border:1px solid #d1d5db !important; border-radius:999px !important;
    padding:.25rem .8rem !important; min-height:2.2rem !important;
}
div[role="radiogroup"] label:has(input:checked) {
    background:#e8f1ff !important; border-color:#0a84ff !important;
}

@media (max-width: 760px) {
    .block-container { padding-left:.45rem; padding-right:.45rem; padding-top:.65rem; }
    [data-testid="stHorizontalBlock"] { flex-wrap:wrap !important; gap:.35rem !important; }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        min-width:100% !important; width:100% !important; flex:1 1 100% !important;
    }
    .hero, .nav-shell, .scan-card, .result-card, [data-testid="stMetric"], [data-testid="stExpander"] { border-radius:18px !important; }
    .stButton > button, .stDownloadButton > button { width:100% !important; min-height:2.95rem !important; }
}


/* V5.9 compact decision cards */
.result-stat-strip { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.45rem; margin:.35rem 0 .75rem 0; }
.result-stat { background:#fff; border:1px solid #e5e7eb; border-radius:15px; padding:.55rem .7rem; }
.result-stat .k { color:#6b7280; font-size:.68rem; font-weight:700; }
.result-stat .v { color:#111827; font-size:1.08rem; font-weight:800; margin-top:.08rem; }
.decision-list { display:flex; flex-direction:column; gap:.45rem; margin-top:.45rem; }
a.decision-card { display:block; text-decoration:none !important; color:inherit !important; background:#fff; border:1px solid #e5e7eb; border-radius:17px; padding:.62rem .72rem; box-shadow:0 3px 12px rgba(17,24,39,.035); transition:transform .08s ease,border-color .08s ease,box-shadow .08s ease; }
a.decision-card:hover { border-color:#0a84ff; box-shadow:0 5px 16px rgba(10,132,255,.08); transform:translateY(-1px); }
.dc-top { display:grid; grid-template-columns:92px 64px minmax(150px,1.2fr) minmax(120px,.8fr); align-items:center; gap:.45rem; }
.dc-symbol { font-size:1rem; font-weight:850; color:#111827; letter-spacing:.01em; }
.dc-score { display:inline-flex; align-items:center; justify-content:center; background:#eef6ff; color:#0068d9; border:1px solid #cfe5ff; border-radius:999px; min-height:28px; font-size:.82rem; font-weight:850; }
.dc-signals { font-size:.78rem; font-weight:750; color:#374151; white-space:normal; }
.dc-strong { font-size:.72rem; color:#6b7280; text-align:right; }
.dc-metrics { display:grid; grid-template-columns:repeat(10,minmax(0,1fr)); gap:.32rem; margin-top:.48rem; }
.dc-metric { background:#f8fafc; border-radius:10px; padding:.33rem .38rem; min-width:0; }
.dc-metric .mk { display:block; color:#94a3b8; font-size:.56rem; font-weight:800; text-transform:uppercase; letter-spacing:.03em; }
.dc-metric .mv { display:block; color:#111827; font-size:.70rem; font-weight:720; margin-top:.06rem; white-space:normal; overflow-wrap:anywhere; }
.dc-note { color:#64748b; font-size:.64rem; margin-top:.35rem; white-space:normal; }
.signal-tag { display:inline-block; margin-right:.18rem; margin-bottom:.14rem; padding:.12rem .34rem; border-radius:999px; background:#f3f4f6; border:1px solid #e5e7eb; color:#374151; font-size:.62rem; font-weight:800; }
.simple-result-card { display:block; text-decoration:none !important; color:inherit !important; background:#fff; border:1px solid #e5e7eb; border-radius:15px; padding:.56rem .65rem; margin:.38rem 0; }
.simple-result-card:hover { border-color:#0a84ff; }
.src-top { display:flex; align-items:center; gap:.45rem; flex-wrap:wrap; }
.src-symbol { font-size:.95rem; font-weight:850; min-width:70px; }
.src-score { color:#0068d9; font-weight:850; }
.src-body { display:flex; flex-wrap:wrap; gap:.28rem; margin-top:.34rem; }
.src-chip { background:#f8fafc; border-radius:9px; padding:.25rem .38rem; font-size:.68rem; color:#334155; }

@media (max-width: 760px) {
  .result-stat-strip { grid-template-columns:repeat(4,minmax(0,1fr)); gap:.25rem; }
  .result-stat { padding:.4rem .38rem; border-radius:12px; text-align:center; }
  .result-stat .k { font-size:.54rem; }
  .result-stat .v { font-size:.9rem; }
  a.decision-card { padding:.55rem .55rem; border-radius:15px; }
  .dc-top { grid-template-columns:72px 52px 1fr; gap:.3rem; }
  .dc-strong { grid-column:1 / -1; text-align:left; font-size:.62rem; margin-top:-.1rem; }
  .dc-symbol { font-size:.9rem; }
  .dc-score { min-height:25px; font-size:.73rem; }
  .dc-signals { font-size:.67rem; }
  .dc-metrics { grid-template-columns:repeat(5,minmax(0,1fr)); gap:.24rem; margin-top:.38rem; }
  .dc-metric { padding:.28rem .25rem; border-radius:8px; }
  .dc-metric .mk { font-size:.48rem; }
  .dc-metric .mv { font-size:.60rem; }
  .dc-note { font-size:.56rem; }
}
@media (max-width: 430px) {
  .dc-metrics { grid-template-columns:repeat(4,minmax(0,1fr)); }
  .result-stat-strip { grid-template-columns:repeat(2,minmax(0,1fr)); }
}

</style>
""",
    unsafe_allow_html=True,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(BASE_DIR, ".vwap_ayarlar.json")
BIST_LIST_PATH = os.path.join(BASE_DIR, "bist_list.txt")
AUTO_SETTINGS_PATH = os.path.join(BASE_DIR, "auto_scan_settings.json")

CURRENCY_LABELS = {
    "TRY": "TL",
    "USD": "USD",
    "EUR": "EUR",
}

DEFAULT_SETTINGS = {
    "period": "weekly",
    "currency": "USD",
    "lookback": 2,
    "max_workers": 20,
    "use_cache": True,
    "sideways_enabled": True,
    "sideways_method": "atr",
    "sideways_months_list": [12, 18, 24],
    "sideways_min_windows": None,
    "sideways_range_pct": 15.0,
    "sideways_atr_pct": 5.0,
    "drawdown_enabled": True,
    "drawdown_min_pct": 50.0,
    "son_semboller_text": "",
    "alt_scan_period": "monthly",
    "alt_scan_min_chain": 3,
    "alt_scan_min_score": 50,
    "tl_scan_period": "1h",
    "tl_scan_pivot_window": 3,
    "tl_scan_min_span_bars": 30,
    "tl_scan_lookback_bars": 200,
    "tl_scan_breakout_lookback": 3,
    "tl_scan_touch_tolerance_pct": 1.5,
    "tl_scan_min_touches": 3,
    "tl_scan_require_volume": True,
    "tl_scan_volume_factor": 1.5,
    "tri_scan_period": "4h",
    "tri_scan_pivot_window": 3,
    "tri_scan_min_span_bars": 28,
    "tri_scan_lookback_bars": 200,
    "tri_scan_min_apex_bars_ahead": 1,
    "tri_scan_max_apex_bars_ahead": 40,
    "tri_scan_max_squeeze_pct": 50.0,
    "last_scan_type": "VWAP",
    "ui_results_view": "Karar Tablosu",
    "result_prefs": {
        "Karar Tablosu": {
            "query": "", "min_signal": 1, "min_score": 0,
            "required_signals": [], "sort": "Sinyal Sayısı ↓",
        },
        "VWAP": {
            "quality": "Tümü", "search": "", "sort": "Yükseliş Puanı ↓",
            "scope": "Tüm", "level": 0,
        },
        "Üçgen": {"quality": "Tümü", "search": "", "sort": "Yükseliş Puanı ↓"},
        "Düşen Trend": {"quality": "Tümü", "search": "", "sort": "Yükseliş Puanı ↓"},
        "Alternasyon": {"quality": "Tümü", "search": "", "sort": "Yükseliş Puanı ↓"},
    },
}


def load_settings():
    cfg = copy.deepcopy(DEFAULT_SETTINGS)
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update(data)
    except Exception:
        pass
    return cfg


def save_partial_settings(updates):
    cfg = load_settings()
    cfg.update(updates)
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def save_partial_settings_if_changed(updates):
    cfg = load_settings()
    changed = any(cfg.get(k) != v for k, v in (updates or {}).items())
    if changed:
        save_partial_settings(updates)



AUTO_SCANNER_SETTING_KEYS = (
    "period", "currency", "lookback", "max_workers", "use_cache",
    "sideways_enabled", "sideways_method", "sideways_months_list", "sideways_min_windows",
    "sideways_range_pct", "sideways_atr_pct", "drawdown_enabled", "drawdown_min_pct",
    "alt_scan_period", "alt_scan_min_chain", "alt_scan_min_score",
    "tl_scan_period", "tl_scan_pivot_window", "tl_scan_min_span_bars", "tl_scan_lookback_bars",
    "tl_scan_breakout_lookback", "tl_scan_touch_tolerance_pct", "tl_scan_require_volume",
    "tl_scan_min_touches", "tl_scan_volume_factor",
    "tri_scan_period", "tri_scan_pivot_window", "tri_scan_min_span_bars", "tri_scan_lookback_bars",
    "tri_scan_min_apex_bars_ahead", "tri_scan_max_apex_bars_ahead", "tri_scan_max_squeeze_pct",
)


def _read_local_auto_defaults():
    try:
        with open(AUTO_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {
            "enabled": True, "timezone": "Europe/Istanbul", "weekdays": [0, 1, 2, 3, 4],
            "times": ["10:05", "10:30", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "17:45"],
            "grace_minutes": 9, "phases": ["VWAP", "Üçgen", "Düşen Trend", "Alternasyon"],
            "min_score": 70, "min_signal_count": 1, "priority_signal_count": 2,
            "max_messages_per_run": 20, "send_summary_when_empty": False, "dedupe_days": 14,
            "link_site_scanner_settings": True, "use_site_symbol_list": False, "scanner_settings": {},
        }


def _secret_value(name, default=""):
    try:
        value = st.secrets.get(name, default)
        if value not in (None, ""):
            return str(value)
    except Exception:
        pass
    return str(os.getenv(name, default) or "")


def github_settings_connection():
    return {
        "token": _secret_value("GITHUB_SETTINGS_TOKEN"),
        "owner": _secret_value("GITHUB_REPO_OWNER", GITHUB_DEFAULT_OWNER),
        "repo": _secret_value("GITHUB_REPO_NAME", GITHUB_DEFAULT_REPO),
    }


def extract_auto_scanner_settings(site_cfg=None, include_symbols=False):
    cfg = site_cfg or load_settings()
    out = {k: copy.deepcopy(cfg.get(k)) for k in AUTO_SCANNER_SETTING_KEYS if k in cfg}
    if include_symbols:
        out["son_semboller_text"] = str(cfg.get("son_semboller_text") or "")
    return out


def load_remote_auto_config(force=False):
    if not force and isinstance(st.session_state.get("_remote_auto_config"), dict):
        return copy.deepcopy(st.session_state["_remote_auto_config"]), st.session_state.get("_remote_auto_error")
    base = _read_local_auto_defaults()
    conn = github_settings_connection()
    if not conn["token"]:
        err = "Streamlit Secrets içinde GITHUB_SETTINGS_TOKEN henüz tanımlı değil."
        st.session_state["_remote_auto_config"] = copy.deepcopy(base)
        st.session_state["_remote_auto_error"] = err
        return base, err
    raw, err = github_get_repo_variable(conn["token"], owner=conn["owner"], repo=conn["repo"], name=AUTO_CONFIG_VARIABLE)
    if err:
        st.session_state["_remote_auto_config"] = copy.deepcopy(base)
        st.session_state["_remote_auto_error"] = err
        return base, err
    remote = decode_auto_config(raw)
    if remote:
        base.update(remote)
    st.session_state["_remote_auto_config"] = copy.deepcopy(base)
    st.session_state["_remote_auto_error"] = None
    return base, None


def save_remote_auto_config(cfg):
    conn = github_settings_connection()
    if not conn["token"]:
        return False, "GITHUB_SETTINGS_TOKEN tanımlı değil."
    ok, err = github_upsert_repo_variable(
        conn["token"], encode_auto_config(cfg), owner=conn["owner"], repo=conn["repo"], name=AUTO_CONFIG_VARIABLE
    )
    if ok:
        st.session_state["_remote_auto_config"] = copy.deepcopy(cfg)
        st.session_state["_remote_auto_error"] = None
    return ok, err


def hydrate_site_scanner_settings_from_remote():
    """Yeni Streamlit oturumunda merkezi otomatik tarama ayarlarını siteye geri taşır."""
    if st.session_state.get("_auto_remote_hydrated"):
        return
    st.session_state["_auto_remote_hydrated"] = True
    cfg, err = load_remote_auto_config(force=True)
    if err or not bool(cfg.get("link_site_scanner_settings", True)):
        return
    remote_scanner = cfg.get("scanner_settings") or {}
    if isinstance(remote_scanner, dict) and remote_scanner:
        save_partial_settings_if_changed({k: copy.deepcopy(v) for k, v in remote_scanner.items() if k in AUTO_SCANNER_SETTING_KEYS})
        if bool(cfg.get("use_site_symbol_list", False)) and "son_semboller_text" in remote_scanner:
            save_partial_settings_if_changed({"son_semboller_text": str(remote_scanner.get("son_semboller_text") or "")})


def sync_linked_auto_scanner_settings(site_cfg=None, quiet=True):
    remote, err = load_remote_auto_config(force=False)
    if err or not bool(remote.get("link_site_scanner_settings", True)):
        return False, err
    include_symbols = bool(remote.get("use_site_symbol_list", False))
    desired = extract_auto_scanner_settings(site_cfg or load_settings(), include_symbols=include_symbols)
    if remote.get("scanner_settings") == desired:
        return True, None
    remote["scanner_settings"] = desired
    ok, save_err = save_remote_auto_config(remote)
    if not ok and not quiet:
        st.error(save_err or "Otomatik tarama ayarları GitHub'a kaydedilemedi.")
    return ok, save_err


def _parse_times_text(text):
    out = []
    bad = []
    for raw in str(text or "").replace(";", ",").split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            hh, mm = [int(x) for x in raw.split(":", 1)]
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                raise ValueError
            val = f"{hh:02d}:{mm:02d}"
            if val not in out:
                out.append(val)
        except Exception:
            bad.append(raw)
    return out, bad


def render_auto_scan_settings_panel():
    remote, remote_err = load_remote_auto_config(force=False)
    conn = github_settings_connection()
    connected = bool(conn.get("token")) and not remote_err

    with st.expander("🤖 Otomatik Tarama ve Telegram", expanded=False):
        if connected:
            st.success("GitHub otomatik tarama ayarlarına bağlı. Burada kaydettiğin değerler bir sonraki otomatik taramada kullanılır.")
        else:
            st.warning("GitHub ayar bağlantısı henüz tamamlanmadı. Önce Streamlit Secrets'a GITHUB_SETTINGS_TOKEN eklemeliyiz.")
            if remote_err:
                st.caption(remote_err)

        enabled = st.checkbox("Otomatik tarama aktif", value=bool(remote.get("enabled", True)), key="auto_enabled")
        link_site = st.checkbox(
            "Normal tarama ayarlarını otomatik taramada da kullan",
            value=bool(remote.get("link_site_scanner_settings", True)), key="auto_link_site",
            help="Açıksa VWAP, Üçgen, Düşen Trend ve Alternasyon ayarlarını sitede değiştirdiğinde GitHub otomatik taraması da aynı ayarları kullanır.",
        )
        use_site_symbols = st.checkbox(
            "Sitedeki hisse listesini de kullan",
            value=bool(remote.get("use_site_symbol_list", False)), key="auto_use_site_symbols",
            help="Kapalı kalırsa otomatik tarama bist_list.txt içindeki tüm listeyi tarar.",
        )

        phases_default = [p for p in remote.get("phases", ["VWAP", "Üçgen", "Düşen Trend", "Alternasyon"]) if p in ["VWAP", "Üçgen", "Düşen Trend", "Alternasyon"]]
        phases = st.multiselect(
            "Otomatik çalışacak taramalar",
            ["VWAP", "Üçgen", "Düşen Trend", "Alternasyon"], default=phases_default,
            key="auto_phases",
        )
        times_text = st.text_input(
            "Tarama saatleri (Türkiye saati)",
            value=",".join(remote.get("times") or []),
            placeholder="10:05,10:30,11:00,12:00,13:00,14:00,15:00,16:00,17:00,17:45",
            key="auto_times_text",
        )
        times, bad_times = _parse_times_text(times_text)
        if bad_times:
            st.error("Geçersiz saat: " + ", ".join(bad_times))

        a1, a2 = st.columns(2)
        with a1:
            min_score = st.slider("Telegram min. yükseliş puanı", 0, 100, int(float(remote.get("min_score", 70))), 5, key="auto_min_score")
            min_signals = st.slider("Telegram min. sinyal sayısı", 1, 4, int(remote.get("min_signal_count", 1)), key="auto_min_signals")
        with a2:
            priority = st.slider("Güçlü bildirim için sinyal", 1, 4, int(remote.get("priority_signal_count", 2)), key="auto_priority")
            max_messages = st.slider("Bir taramada maks. Telegram mesajı", 1, 50, int(remote.get("max_messages_per_run", 20)), key="auto_max_messages")
        b1, b2 = st.columns(2)
        with b1:
            dedupe_days = st.slider("Aynı sinyali tekrar göndermeme (gün)", 1, 60, int(remote.get("dedupe_days", 14)), key="auto_dedupe_days")
        with b2:
            summary_empty = st.checkbox("Sinyal yoksa da özet gönder", value=bool(remote.get("send_summary_when_empty", False)), key="auto_empty_summary")

        if link_site:
            current = load_settings()
            st.caption(
                "Bağlı tarama ayarları: "
                f"VWAP {PERIOD_LABELS.get(current.get('period'), current.get('period'))} · "
                f"Üçgen {TRIANGLE_SCAN_PERIOD_LABELS.get(current.get('tri_scan_period'), current.get('tri_scan_period'))} · "
                f"Trend {TRENDLINE_SCAN_PERIOD_LABELS.get(current.get('tl_scan_period'), current.get('tl_scan_period'))} · "
                f"Alternasyon {ALTERNATION_SCAN_PERIOD_LABELS.get(current.get('alt_scan_period'), current.get('alt_scan_period'))}"
            )

        save_disabled = bool(bad_times) or not times or not phases or not connected
        if st.button("Otomatik Tarama Ayarlarını Kaydet", type="primary", width="stretch", disabled=save_disabled, key="auto_save_settings"):
            new_cfg = copy.deepcopy(remote)
            new_cfg.update({
                "enabled": bool(enabled),
                "timezone": "Europe/Istanbul",
                "weekdays": [0, 1, 2, 3, 4],
                "times": times,
                "phases": phases,
                "scan_mode": "Tümünü Tara" if len(phases) > 1 else phases[0],
                "min_score": int(min_score),
                "min_signal_count": int(min_signals),
                "priority_signal_count": int(priority),
                "max_messages_per_run": int(max_messages),
                "send_summary_when_empty": bool(summary_empty),
                "dedupe_days": int(dedupe_days),
                "link_site_scanner_settings": bool(link_site),
                "use_site_symbol_list": bool(use_site_symbols),
            })
            if link_site:
                new_cfg["scanner_settings"] = extract_auto_scanner_settings(load_settings(), include_symbols=use_site_symbols)
            ok, err = save_remote_auto_config(new_cfg)
            if ok:
                st.success("Kaydedildi. Bir sonraki GitHub Actions taraması bu ayarlarla çalışacak.")
            else:
                st.error(err or "Ayarlar kaydedilemedi.")

        st.markdown("---")
        reset_confirm = st.checkbox("Otomatik tarama ayarlarını varsayılana döndürmeyi onaylıyorum", key="auto_reset_confirm")
        if st.button("Otomatik Tarama Ayarlarını Sıfırla", width="stretch", disabled=(not reset_confirm or not connected), key="auto_reset_button"):
            defaults = _read_local_auto_defaults()
            if bool(defaults.get("link_site_scanner_settings", True)):
                defaults["scanner_settings"] = extract_auto_scanner_settings(load_settings(), include_symbols=bool(defaults.get("use_site_symbol_list", False)))
            ok, err = save_remote_auto_config(defaults)
            if ok:
                for k in list(st.session_state.keys()):
                    if str(k).startswith("auto_"):
                        st.session_state.pop(k, None)
                st.success("Otomatik tarama ayarları varsayılana döndürüldü.")
                st.rerun()
            else:
                st.error(err or "Sıfırlama başarısız.")


def get_result_pref(view, key, default=None):
    cfg = load_settings()
    prefs = cfg.get("result_prefs") or {}
    view_prefs = prefs.get(view) or {}
    return copy.deepcopy(view_prefs.get(key, default))


def save_result_pref(view, key, value):
    cfg = load_settings()
    prefs = copy.deepcopy(cfg.get("result_prefs") or {})
    view_prefs = copy.deepcopy(prefs.get(view) or {})
    if view_prefs.get(key) == value:
        return
    view_prefs[key] = copy.deepcopy(value)
    prefs[view] = view_prefs
    save_partial_settings({"result_prefs": prefs})


def init_widget_state(widget_key, value):
    if widget_key not in st.session_state:
        st.session_state[widget_key] = copy.deepcopy(value)


def persist_result_widget(view, pref_key, widget_key):
    save_result_pref(view, pref_key, st.session_state.get(widget_key))


def persist_global_widget(setting_key, widget_key):
    save_partial_settings_if_changed({setting_key: st.session_state.get(widget_key)})


def reset_all_settings():
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(copy.deepcopy(DEFAULT_SETTINGS), f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    prefixes = (
        "decision_", "quality_", "search_", "sort_", "vwap_", "tri_", "tl_", "alt_",
        "general_", "symbol_list_text", "results_view_select", "scan_type_select",
        "reset_settings_",
    )
    for key in list(st.session_state.keys()):
        if any(str(key).startswith(prefix) for prefix in prefixes):
            st.session_state.pop(key, None)
    st.session_state["_scan_type"] = DEFAULT_SETTINGS["last_scan_type"]
    st.session_state["_results_focus"] = DEFAULT_SETTINGS["ui_results_view"]
    st.session_state["_settings_reset_notice"] = True
    st.rerun()


def read_bist_list_text():
    try:
        with open(BIST_LIST_PATH, "r", encoding="utf-8-sig") as f:
            text = f.read().strip()
        if text:
            return text
    except Exception:
        pass
    return "\n".join(DEFAULT_SYMBOLS)


def symbol_text_from_settings(cfg):
    text = str(cfg.get("son_semboller_text") or "").strip()
    return text or read_bist_list_text()


def q_score(r):
    try:
        return float(((r or {}).get("quality") or {}).get("score") or 0.0)
    except Exception:
        return 0.0


def q_grade(r):
    q = (r or {}).get("quality") or {}
    grade = q.get("grade", "—")
    label = q.get("label", "—")
    return f"{grade} · {label}"


def q_reasons(r, limit=3):
    return " · ".join((((r or {}).get("quality") or {}).get("reasons") or [])[:limit]) or "—"


def enrich_actual_ath_drawdown(row, min_pct=60.0):
    """VWAP stratejisini değiştirmeden sonuçtaki df üzerinden gerçek pencere ATH düşüşünü ekler."""
    row = row or {}
    df = row.get("df")
    try:
        if df is not None and len(df) and "High" in df.columns and "Close" in df.columns:
            highs = pd.to_numeric(df["High"], errors="coerce")
            closes = pd.to_numeric(df["Close"], errors="coerce")
            if highs.notna().any() and closes.notna().any():
                ath_idx = highs.idxmax()
                ath_price = float(highs.loc[ath_idx])
                last_close = float(closes.dropna().iloc[-1])
                if ath_price > 0:
                    pct = max(0.0, (ath_price - last_close) / ath_price * 100.0)
                    try:
                        ath_date = str(pd.Timestamp(df.loc[ath_idx, "Date"]).date()) if "Date" in df.columns else str(pd.Timestamp(ath_idx).date())
                    except Exception:
                        ath_date = "—"
                    row["drawdown"] = {
                        "is_drawdown": pct >= float(min_pct or 0),
                        "drawdown_pct": round(pct, 1),
                        "anchor_date": ath_date,
                        "anchor_reason": "ATH",
                    }
    except Exception:
        pass
    return row


def vwap_filter_passes(row, cfg):
    """VWAP zincir mantığını değiştirmeden, kullanıcı seçtiyse sonuç sonrasında filtre uygular."""
    row = enrich_actual_ath_drawdown(row or {}, cfg.get("drawdown_min_pct", 50.0))
    if bool(cfg.get("sideways_enabled", False)):
        sw = row.get("sideways") or {}
        if not bool(sw.get("is_sideways", False)):
            return False
    if bool(cfg.get("drawdown_enabled", False)):
        dd = row.get("drawdown") or {}
        if not bool(dd.get("is_drawdown", False)):
            return False
    return True


def format_sideways_status(row):
    sw = (row or {}).get("sideways") or {}
    if not sw:
        return "—"
    ok = bool(sw.get("is_sideways", False))
    count = sw.get("sideways_count")
    total = sw.get("total_windows")
    months = sw.get("sideways_months") or []
    detail = f"{count}/{total}" if count is not None and total is not None else ""
    month_txt = ",".join(str(x) for x in months) + " ay" if months else ""
    extra = " · ".join(x for x in (detail, month_txt) if x)
    return ("✅ Yatay" if ok else "❌ Değil") + (f" · {extra}" if extra else "")


def format_drawdown_value(row):
    dd = (row or {}).get("drawdown") or {}
    val = dd.get("drawdown_pct")
    if val is None:
        return "—"
    try:
        return round(float(val), 1)
    except Exception:
        return val


def build_combined_chart_payload(symbol, signal_map):
    payload = {"symbol": str(symbol or "—"), "signals": {}}
    for name in ("VWAP", "Üçgen", "Düşen Trend", "Alternasyon"):
        item = (signal_map or {}).get(name)
        if isinstance(item, dict):
            payload["signals"][name] = item
    return payload


def collect_signal_results_for_symbol(sets, symbol):
    sym = str(symbol or "").replace(".IS", "").upper()
    out = {}
    for name in ("VWAP", "Üçgen", "Düşen Trend", "Alternasyon"):
        for r in list((sets or {}).get(name) or []):
            rs = str((r or {}).get("symbol") or "").replace(".IS", "").upper()
            if rs == sym:
                out[name] = r
                break
    return out


def _safe_num(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _fmt_cell(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return f"{v:.1f}"
    s = str(v).strip()
    return s if s else "—"


def render_compact_table(df, header_map=None, note=None, key_prefix="table", link_symbol_col=None):
    if df is None or df.empty:
        st.warning("Gösterilecek veri yok.")
        return
    header_map = header_map or {}
    cols = list(df.columns)
    thead = "".join(f"<th>{html.escape(str(header_map.get(c, c)))}</th>" for c in cols)
    body_rows = []
    for _, row in df.iterrows():
        symbol = str(row.get(link_symbol_col) or "").replace(".IS", "") if link_symbol_col else ""
        href = f"?open={html.escape(symbol)}" if symbol else ""
        tds = []
        for c in cols:
            val = html.escape(_fmt_cell(row.get(c)))
            if href:
                val = f'<a class="row-open-link" href="{href}" target="_self">{val}</a>'
            tds.append(f"<td>{val}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    note_html = f'<div class="compact-result-note">{html.escape(str(note))}</div>' if note else ''
    table_html = '<div class="compact-result-wrap">' + note_html + '<table class="compact-result-table"><thead><tr>' + thead + '</tr></thead><tbody>' + ''.join(body_rows) + '</tbody></table></div>'
    st.markdown(table_html, unsafe_allow_html=True)



def _esc(v):
    return html.escape(_fmt_cell(v))


def render_result_stats(combined_rows):
    total = len(combined_rows or [])
    s2 = sum(int(r.get("Sinyal Sayısı") or 0) >= 2 for r in (combined_rows or []))
    p70 = sum(float(r.get("En Yüksek Puan") or 0) >= 70 for r in (combined_rows or []))
    s3 = sum(int(r.get("Sinyal Sayısı") or 0) >= 3 for r in (combined_rows or []))
    st.markdown(
        f'<div class="result-stat-strip">'
        f'<div class="result-stat"><div class="k">HİSSE</div><div class="v">{total}</div></div>'
        f'<div class="result-stat"><div class="k">2+ SİNYAL</div><div class="v">{s2}</div></div>'
        f'<div class="result-stat"><div class="k">70+ PUAN</div><div class="v">{p70}</div></div>'
        f'<div class="result-stat"><div class="k">3+ SİNYAL</div><div class="v">{s3}</div></div>'
        f'</div>', unsafe_allow_html=True
    )


def _signal_tags(row):
    text = str(row.get("Teyitler") or "—")
    if text == "—":
        return '<span class="signal-tag">—</span>'
    parts = [x.strip() for x in text.split("+") if x.strip()]
    short = {"Düşen Trend": "TREND", "Alternasyon": "ALT", "Üçgen": "ÜÇG", "VWAP": "VWAP"}
    return ''.join(f'<span class="signal-tag">{html.escape(short.get(p,p))}</span>' for p in parts)


def _metric_html(label, value):
    return f'<div class="dc-metric"><span class="mk">{html.escape(str(label))}</span><span class="mv">{_esc(value)}</span></div>'


def render_decision_cards(rows):
    if not rows:
        st.warning("Bu filtrelere uyan hisse yok.")
        return
    for idx, r in enumerate(rows):
        sym = str(r.get("Sembol") or "—").replace(".IS", "")
        score = _fmt_cell(r.get("En Yüksek Puan"))
        avg = _fmt_cell(r.get("Ortalama Puan"))
        strong = _fmt_cell(r.get("En Güçlü Sinyal"))
        signal_count = int(r.get("Sinyal Sayısı") or 0)
        signals_txt = str(r.get("Teyitler") or "—")
        with st.container(border=True):
            if st.button(
                f"{sym}  ·  {score} puan  ·  {signal_count} sinyal  ·  {signals_txt}",
                key=f"decision_card_open_{sym}_{idx}",
                width="stretch",
                type="secondary",
            ):
                if r.get("_chart_kind") == "combined":
                    open_chart("combined", sym, r.get("_chart_payload"))
                else:
                    chart_view = r.get("_chart_view")
                    result = r.get("_chart_result")
                    if chart_view and result:
                        open_chart(chart_kind_for(chart_view), sym, result)
            alt = r.get("Alternasyon") or "—"
            alt_score = r.get("Alternasyon Desen Puanı")
            if alt_score not in (None, "—", ""):
                alt = f"{alt} / {alt_score}"
            metrics = ''.join([
                _metric_html("VWAP", r.get("VWAP", "—")),
                _metric_html("Düşüş", (str(r.get("ATH'den Düşüş %", "—")) + "%") if r.get("ATH'den Düşüş %") not in (None,"—","") else "—"),
                _metric_html("Yatay", r.get("Yataylık", "—")),
                _metric_html("Üçgen", r.get("Üçgen", "—")),
                _metric_html("Trend", r.get("Düşen Kırılım", "—")),
                _metric_html("Alt", alt),
                _metric_html("RSI", r.get("RSI 14", "—")),
                _metric_html("Hacim", r.get("Hacim Oranı", "—")),
                _metric_html("Direnç", (str(r.get("Dirence Alan %", "—")) + "%") if r.get("Dirence Alan %") not in (None,"—","") else "—"),
                _metric_html("Retest", r.get("Retest", "—")),
            ])
            note = r.get("Güçlü Teyitler")
            note_html = f'<div class="dc-note">{html.escape(str(note))}</div>' if note not in (None,"—","") else ''
            st.markdown(
                f'<div class="dc-top"><div class="dc-strong">güçlü {html.escape(str(strong))} · ort {html.escape(str(avg))}</div></div>'
                f'<div class="dc-metrics">{metrics}</div>{note_html}',
                unsafe_allow_html=True,
            )

def render_simple_signal_cards(view, rows):
    if not rows:
        st.warning("Bu filtreye uyan sonuç yok.")
        return
    for idx, r in enumerate(rows):
        sym = str((r or {}).get("symbol") or "—").replace(".IS", "")
        score = round(q_score(r), 1)
        chips = []
        if view == "VWAP":
            chips = [f"{r.get('level','—')}. VWAP", f"Bar {r.get('bars_ago','—')}", f"Düşüş {format_drawdown_value(r)}%", format_sideways_status(r)]
        elif view == "Üçgen":
            chips = [r.get("pattern_type","—"), f"Sıkışma {r.get('squeeze_pct','—')}%", f"Apex {r.get('apex_bars_ahead','—')}"]
        elif view == "Düşen Trend":
            chips = [f"Temas {r.get('touches','—')}", f"Bar {r.get('bars_ago','—')}", r.get("cross_date","—")]
        elif view == "Alternasyon":
            chips = [f"Zincir {r.get('chain_length','—')}", f"Desen {r.get('score','—')}", f"Örtüşme {r.get('mean_body_overlap_pct','—')}%"]
        elif view == "Özet":
            chips = [q_reasons(r)]
        with st.container(border=True):
            if st.button(
                f"{sym}  ·  {score} puan  ·  {q_grade(r)}",
                key=f"signal_card_open_{view}_{sym}_{idx}",
                width="stretch",
                type="secondary",
            ):
                signals = collect_signal_results_for_symbol(st.session_state._result_sets, sym)
                if len(signals) >= 2:
                    open_chart("combined", sym, build_combined_chart_payload(sym, signals))
                elif view in {"VWAP", "Üçgen", "Düşen Trend", "Alternasyon"}:
                    open_chart(chart_kind_for(view), sym, r)
                elif signals:
                    name, result = next(iter(signals.items()))
                    open_chart(chart_kind_for(name), sym, result)
            body = ''.join(f'<span class="src-chip">{html.escape(_fmt_cell(x))}</span>' for x in chips)
            st.markdown(f'<div class="src-body">{body}</div>', unsafe_allow_html=True)

def sort_combined_rows(rows, mode):
    rows = list(rows or [])
    if mode == "Sinyal Sayısı ↓":
        rows.sort(key=lambda r: (int(r.get("Sinyal Sayısı") or 0), _safe_num(r.get("En Yüksek Puan")), _safe_num(r.get("Ortalama Puan"))), reverse=True)
    elif mode == "En Yüksek Puan ↓":
        rows.sort(key=lambda r: (_safe_num(r.get("En Yüksek Puan")), int(r.get("Sinyal Sayısı") or 0)), reverse=True)
    elif mode == "Ortalama Puan ↓":
        rows.sort(key=lambda r: (_safe_num(r.get("Ortalama Puan")), _safe_num(r.get("En Yüksek Puan"))), reverse=True)
    elif mode == "RSI 14 ↓":
        rows.sort(key=lambda r: (_safe_num(r.get("RSI 14")), _safe_num(r.get("En Yüksek Puan"))), reverse=True)
    elif mode == "Hacim Oranı ↓":
        rows.sort(key=lambda r: (_safe_num(r.get("Hacim Oranı")), _safe_num(r.get("En Yüksek Puan"))), reverse=True)
    elif mode == "ATH / Anchor Düşüş ↓":
        rows.sort(key=lambda r: (_safe_num(r.get("ATH'den Düşüş %")), _safe_num(r.get("En Yüksek Puan"))), reverse=True)
    else:
        rows.sort(key=lambda r: str(r.get("Sembol") or ""))
    return rows


def sort_view_rows(view, rows, mode):
    rows = list(rows or [])
    if mode == "Sembol A-Z":
        rows.sort(key=lambda r: str((r or {}).get("symbol") or ""))
        return rows
    if view == "VWAP":
        if mode == "VWAP Seviyesi ↓":
            rows.sort(key=lambda r: (int((r or {}).get("level") or 0), q_score(r)), reverse=True)
        elif mode == "Bar Önce ↑":
            rows.sort(key=lambda r: (int((r or {}).get("bars_ago") or 999999), -q_score(r)))
        elif mode == "ATH / Anchor Düşüş ↓":
            rows.sort(key=lambda r: _safe_num(format_drawdown_value(r)), reverse=True)
        else:
            rows.sort(key=q_score, reverse=True)
    elif view == "Üçgen":
        if mode == "Sıkışma % ↑":
            rows.sort(key=lambda r: (_safe_num((r or {}).get("squeeze_pct"), 999999), -q_score(r)))
        else:
            rows.sort(key=q_score, reverse=True)
    elif view == "Düşen Trend":
        if mode == "Temas ↓":
            rows.sort(key=lambda r: (int((r or {}).get("touches") or 0), q_score(r)), reverse=True)
        elif mode == "Bar Önce ↑":
            rows.sort(key=lambda r: (int((r or {}).get("bars_ago") or 999999), -q_score(r)))
        else:
            rows.sort(key=q_score, reverse=True)
    elif view == "Alternasyon":
        if mode == "Desen Puanı ↓":
            rows.sort(key=lambda r: (_safe_num((r or {}).get("score")), q_score(r)), reverse=True)
        elif mode == "Zincir ↓":
            rows.sort(key=lambda r: (int((r or {}).get("chain_length") or 0), q_score(r)), reverse=True)
        else:
            rows.sort(key=q_score, reverse=True)
    else:
        rows.sort(key=q_score, reverse=True)
    return rows


def chart_choice_label_from_combined(row):
    return f"{row.get('Sembol', '—')} · {row.get('Teyitler', '—')} · max {row.get('En Yüksek Puan', '—')}"


def chart_choice_label_from_result(r, view):
    sym = str((r or {}).get('symbol') or '—')
    extra = view
    if view == 'VWAP':
        extra = f"{r.get('level', '—')}. VWAP"
    elif view == 'Üçgen':
        extra = str(r.get('pattern_type') or 'Üçgen')
    elif view == 'Düşen Trend':
        extra = f"Temas {r.get('touches', '—')}"
    elif view == 'Alternasyon':
        extra = f"Zincir {r.get('chain_length', '—')}"
    return f"{sym} · {extra} · puan {round(q_score(r),1)}"


def build_combined_analysis(sets):
    """Tüm tarama sonuçlarını sembol bazında tek karar kaydında birleştirir."""
    by_sym = {}
    signal_scores = {}

    def rec(sym):
        sym = str(sym or "—").replace(".IS", "").upper()
        return by_sym.setdefault(sym, {
            "Sembol": sym,
            "Sinyal Sayısı": 0,
            "Teyitler": "—",
            "VWAP": "—",
            "VWAP Kırılım": "—",
            "VWAP Bar Önce": "—",
            "ATH'den Düşüş %": "—",
            "Yataylık": "—",
            "Üçgen": "—",
            "Üçgen Sıkışma %": "—",
            "Düşen Kırılım": "—",
            "Trend Temas": "—",
            "Alternasyon": "—",
            "Alternasyon Desen Puanı": "—",
            "VWAP Puan": "—",
            "Üçgen Puan": "—",
            "Trend Puan": "—",
            "Alternasyon Puan": "—",
            "Ortalama Puan": 0.0,
            "En Yüksek Puan": 0.0,
            "En Güçlü Sinyal": "—",
            "RSI 14": "—",
            "Dirence Alan %": "—",
            "Hacim Oranı": "—",
            "Retest": "—",
            "Güçlü Teyitler": "—",
            "Kalite": "—",
            "_chart_view": None,
            "_chart_result": None,
            "_chart_kind": None,
            "_chart_payload": None,
            "_signal_results": {},
        })

    # Bağımsız yardımcı sonuçlar — VWAP eşleşmesi olmasa da korunur.
    for r in list(sets.get("Yataylık") or []):
        x = rec(r.get("symbol"))
        cnt = r.get("sideways_count", 0); tot = r.get("total_windows", 0)
        months = ",".join(str(m) for m in (r.get("sideways_months") or []))
        x["Yataylık"] = f"✅ {cnt}/{tot}" + (f" · {months} ay" if months else "")

    for r in list(sets.get("ATH'den Düşüş") or []):
        x = rec(r.get("symbol"))
        val = r.get("drawdown_pct")
        x["ATH'den Düşüş %"] = round(float(val), 1) if val is not None else "—"

    for r in list(sets.get("VWAP") or []):
        x = rec(r.get("symbol"))
        x["VWAP"] = f"{r.get('level', '—')}. VWAP"
        x["VWAP Kırılım"] = r.get("cross_date", "—")
        x["VWAP Bar Önce"] = r.get("bars_ago", "—")
        x["ATH'den Düşüş %"] = format_drawdown_value(r)
        x["Yataylık"] = format_sideways_status(r)
        score = round(q_score(r), 1)
        x["VWAP Puan"] = score
        signal_scores.setdefault(x["Sembol"], []).append((score, "VWAP", "VWAP", r))
        x["_signal_results"]["VWAP"] = r

    for r in list(sets.get("Üçgen") or []):
        x = rec(r.get("symbol"))
        x["Üçgen"] = str(r.get("pattern_type") or "Evet")
        x["Üçgen Sıkışma %"] = r.get("squeeze_pct", "—")
        score = round(q_score(r), 1)
        x["Üçgen Puan"] = score
        signal_scores.setdefault(x["Sembol"], []).append((score, "Üçgen", "Üçgen", r))
        x["_signal_results"]["Üçgen"] = r

    for r in list(sets.get("Düşen Trend") or []):
        x = rec(r.get("symbol"))
        date = r.get("cross_date")
        x["Düşen Kırılım"] = f"✅{f' · {date}' if date else ''}"
        x["Trend Temas"] = r.get("touches", "—")
        score = round(q_score(r), 1)
        x["Trend Puan"] = score
        signal_scores.setdefault(x["Sembol"], []).append((score, "Düşen Trend", "Düşen Trend", r))
        x["_signal_results"]["Düşen Trend"] = r

    for r in list(sets.get("Alternasyon") or []):
        x = rec(r.get("symbol"))
        chain = r.get("chain_length")
        x["Alternasyon"] = f"✅{f' · {chain} mum' if chain else ''}"
        x["Alternasyon Desen Puanı"] = r.get("score", "—")
        score = round(q_score(r), 1)
        x["Alternasyon Puan"] = score
        signal_scores.setdefault(x["Sembol"], []).append((score, "Alternasyon", "Alternasyon", r))
        x["_signal_results"]["Alternasyon"] = r

    for sym, x in by_sym.items():
        choices = signal_scores.get(sym) or []
        if not choices:
            continue
        choices = sorted(choices, key=lambda z: z[0], reverse=True)
        x["Sinyal Sayısı"] = len(choices)
        x["Teyitler"] = " + ".join(c[1] for c in choices)
        x["Ortalama Puan"] = round(sum(c[0] for c in choices) / len(choices), 1)
        best = choices[0]
        x["En Yüksek Puan"] = best[0]
        x["En Güçlü Sinyal"] = best[1]
        x["_chart_view"] = best[2]
        x["_chart_result"] = best[3]
        x["_chart_kind"] = "combined" if len(x.get("_signal_results") or {}) >= 2 else chart_kind_for(best[2])
        x["_chart_payload"] = build_combined_chart_payload(sym, x.get("_signal_results") or {})
        q = (best[3] or {}).get("quality") or {}
        x["RSI 14"] = q.get("rsi14") if q.get("rsi14") is not None else "—"
        x["Dirence Alan %"] = q.get("resistance_room_pct") if q.get("resistance_room_pct") is not None else "—"
        x["Hacim Oranı"] = q.get("volume_ratio") if q.get("volume_ratio") is not None else "—"
        x["Retest"] = "✅" if q.get("retest_confirmed") else "—"
        x["Güçlü Teyitler"] = " · ".join((q.get("reasons") or [])[:3]) or "—"
        x["Kalite"] = q.get("grade") or q_grade(best[3])

    # Önce çoklu teyit, sonra güçlü puan.
    return sorted(
        by_sym.values(),
        key=lambda x: (int(x.get("Sinyal Sayısı") or 0), float(x.get("En Yüksek Puan") or 0), float(x.get("Ortalama Puan") or 0)),
        reverse=True,
    )

def normalize_error_entry(item):
    """Eski/yeni worker hata biçimlerini güvenle (sembol, mesaj) çiftine çevirir."""
    # Eski V4.6 worker bazı tuple kayıtlarını str(tuple) olarak diske yazdı.
    if isinstance(item, str):
        text = item.strip()
        if text.startswith(("(", "[", "{")):
            try:
                parsed = ast.literal_eval(text)
            except Exception:
                parsed = None
            if parsed is not None and parsed is not item:
                return normalize_error_entry(parsed)
        if ": " in text:
            sym, msg = text.split(": ", 1)
            return (sym.strip() or "—", msg.strip() or "Bilinmeyen hata")
        return ("—", text or "Bilinmeyen hata")

    if isinstance(item, dict):
        sym = item.get("symbol") or item.get("sym") or item.get("ticker") or item.get("code") or "—"
        msg = item.get("error") or item.get("message") or item.get("detail") or item.get("reason")
        if msg is None:
            msg = json.dumps(item, ensure_ascii=False, default=str)
        return (str(sym), str(msg))

    if isinstance(item, (list, tuple)):
        if len(item) >= 2:
            sym = item[0] if item[0] not in (None, "") else "—"
            msg = " | ".join(str(x) for x in item[1:] if x not in (None, "")) or "Bilinmeyen hata"
            return (str(sym), msg)
        if len(item) == 1:
            return ("—", str(item[0]))
        return ("—", "Bilinmeyen hata")

    return ("—", str(item) if item is not None else "Bilinmeyen hata")


def handle_open_symbol_query():
    try:
        raw = st.query_params.get("open")
        if isinstance(raw, (list, tuple)):
            raw = raw[-1] if raw else None
        sym = str(raw or "").replace(".IS", "").strip().upper()
    except Exception:
        sym = ""
    if not sym:
        return False
    ensure_result_store()
    signals = collect_signal_results_for_symbol(st.session_state._result_sets, sym)
    if not signals:
        return False
    if len(signals) >= 2:
        st.session_state["_chart_page"] = {"kind": "combined", "symbol": sym, "result": build_combined_chart_payload(sym, signals)}
    else:
        name, result = next(iter(signals.items()))
        st.session_state["_chart_page"] = {"kind": chart_kind_for(name), "symbol": sym, "result": result}
    try:
        del st.query_params["open"]
    except Exception:
        pass
    st.rerun()
    return True


def restore_latest_results_if_needed():
    ensure_result_store()
    if any(st.session_state._result_sets.get(n) is not None for n in ["VWAP", "Üçgen", "Düşen Trend", "Alternasyon"]):
        return False
    try:
        snap = get_scan_job_manager().latest_snapshot()
    except Exception:
        snap = None
    if not snap:
        return False
    result_sets = snap.get("result_sets") or {}
    if not any(result_sets.get(n) is not None for n in ["VWAP", "Üçgen", "Düşen Trend", "Alternasyon"]):
        return False
    _sync_job_results(snap)
    st.session_state["_active_job_id"] = snap.get("id")
    try:
        if snap.get("id"):
            st.query_params["job"] = str(snap.get("id"))
    except Exception:
        pass
    return True


def ensure_result_store():
    st.session_state.setdefault("_result_sets", {})
    st.session_state.setdefault("_result_meta", {})


def store_result_set(name, rows, *, total, period, errors=None, source="Tarama", currency=None, meta_extra=None):
    ensure_result_store()
    st.session_state._result_sets[name] = list(rows or [])
    meta = {
        "total": int(total or 0),
        "period": period,
        "errors": list(errors or []),
        "source": source,
        "currency": currency,
        "scan_time": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }
    if meta_extra:
        meta.update(dict(meta_extra))
    st.session_state._result_meta[name] = meta


def set_page(page, scan_type=None, result_focus=None):
    st.session_state["_app_page"] = page
    if scan_type:
        st.session_state["_scan_type"] = scan_type
    if result_focus:
        st.session_state["_results_focus"] = result_focus
    st.rerun()



# -----------------------------------------------------------------------------
# Mobil / bağlantı kopmasına dayanıklı arka plan taraması
# -----------------------------------------------------------------------------
def _job_query_id():
    try:
        value = st.query_params.get("job")
        if isinstance(value, (list, tuple)):
            value = value[-1] if value else None
        return str(value).strip() if value else None
    except Exception:
        return None


def _attach_job(job_id):
    if not job_id:
        return
    st.session_state["_active_job_id"] = str(job_id)
    try:
        st.query_params["job"] = str(job_id)
    except Exception:
        pass


def _sync_job_results(snapshot):
    if not snapshot:
        return False
    ensure_result_store()
    changed = False
    for name, rows in (snapshot.get("result_sets") or {}).items():
        if st.session_state._result_sets.get(name) is not rows:
            st.session_state._result_sets[name] = rows
            changed = True
    for name, meta in (snapshot.get("result_meta") or {}).items():
        st.session_state._result_meta[name] = meta
        changed = True
    st.session_state["_synced_job_revision"] = int(snapshot.get("revision") or 0)
    return changed


def _resolve_job_snapshot(auto_attach_running=True):
    manager = get_scan_job_manager()
    job_id = _job_query_id() or st.session_state.get("_active_job_id")
    snap = manager.snapshot(job_id) if job_id else None
    if not snap and auto_attach_running:
        # Mobil tarayıcı URL query parametresini kaybetmişse sunucuda hâlâ devam
        # eden tek taramaya yeniden bağlan. Bu uygulama tek tarama işini aynı
        # anda çalıştırdığı için güvenli ve kullanıcı dostu bir geri kazanımdır.
        snap = manager.active_snapshot()
        if snap:
            _attach_job(snap.get("id"))
    if snap:
        _attach_job(snap.get("id"))
        revision = int(snap.get("revision") or 0)
        if revision != int(st.session_state.get("_synced_job_revision") or -1):
            _sync_job_results(snap)
    return snap


def _clear_results_for_job(kind):
    ensure_result_store()
    targets = ["VWAP", "Üçgen", "Düşen Trend", "Alternasyon"] if kind == "Tümünü Tara" else [kind]
    for name in targets:
        st.session_state._result_sets.pop(name, None)
        st.session_state._result_meta.pop(name, None)


def launch_background_scan(kind, symbols, cfg, result_focus=None):
    manager = get_scan_job_manager()
    _clear_results_for_job(kind)
    job_id, started = manager.start(kind, list(symbols), dict(cfg))
    _attach_job(job_id)
    st.session_state["_synced_job_revision"] = -1
    st.session_state["_app_page"] = "Sonuçlar"
    st.session_state["_results_focus"] = result_focus or ("Karar Tablosu" if kind == "Tümünü Tara" else kind)
    if not started:
        st.session_state["_job_start_notice"] = "Sunucuda zaten devam eden bir tarama vardı; ona yeniden bağlandım."
    st.rerun()


@st.fragment(run_every=2.0)
def render_live_scan_status():
    snap = _resolve_job_snapshot(auto_attach_running=True)
    if not snap:
        return
    status = snap.get("status")
    progress = float(snap.get("progress") or 0.0)
    kind = snap.get("kind") or "Tarama"
    detail = snap.get("detail") or ""

    if status in {"queued", "running"}:
        st.markdown(
            f"<div class='compact-status'><strong>{kind}</strong> çalışıyor · %{progress*100:.0f}<br><span class='small-muted'>{detail or 'Tarama sürüyor'}</span></div>",
            unsafe_allow_html=True,
        )
        st.progress(max(0.0, min(1.0, progress)))
        return

    revision = int(snap.get("revision") or 0)
    seen_key = f"{snap.get('id')}:{revision}:{status}"
    if st.session_state.get("_job_terminal_seen") != seen_key:
        _sync_job_results(snap)
        st.session_state["_job_terminal_seen"] = seen_key
        st.rerun()

    if status == "completed":
        total_found = sum(len(v or []) for v in (snap.get("result_sets") or {}).values())
        st.success(f"{kind} tamamlandı · {total_found} sonuç")
    elif status == "failed":
        st.error(f"{kind} durdu · {snap.get('error') or 'Bilinmeyen hata'}")


# -----------------------------------------------------------------------------
# Grafik sayfası
# -----------------------------------------------------------------------------
def chart_payload_complete(kind, result):
    if not isinstance(result, dict):
        return False
    if kind == "combined":
        signals = result.get("signals") or {}
        return any(isinstance((item or {}).get("df"), pd.DataFrame) and len((item or {}).get("df")) > 0 for item in signals.values())
    required = {
        "vwap": ("df", "chain"),
        "alternation": ("df", "start_idx", "end_idx"),
        "trendline": ("df", "line", "cross_idx"),
        "triangle": ("df", "upper", "lower", "apex_x", "apex_y"),
    }.get(kind, ())
    return bool(required) and all(result.get(k) is not None for k in required)


def repair_chart_payload(kind, sym, result):
    if chart_payload_complete(kind, result):
        return result
    if kind == "vwap":
        return result

    cfg = load_settings()
    period = (result or {}).get("period") or {
        "alternation": cfg.get("alt_scan_period", "monthly"),
        "trendline": cfg.get("tl_scan_period", "1h"),
        "triangle": cfg.get("tri_scan_period", "4h"),
    }.get(kind)
    yf_symbol = str(sym).upper().strip()
    if not yf_symbol.endswith(".IS"):
        yf_symbol += ".IS"

    try:
        if kind == "alternation":
            out = fetch_and_scan_alternation_only(
                yf_symbol, period, use_cache=bool(cfg.get("use_cache", True)),
                min_chain=int(cfg.get("alt_scan_min_chain", 3)),
                min_score=cfg.get("alt_scan_min_score"),
            )
        elif kind == "trendline":
            out = fetch_and_scan_trendline_only(
                yf_symbol, period, use_cache=bool(cfg.get("use_cache", True)),
                pivot_window=int(cfg.get("tl_scan_pivot_window", 3)),
                min_span_bars=int(cfg.get("tl_scan_min_span_bars", 30)),
                lookback_bars=int(cfg.get("tl_scan_lookback_bars", 200)),
                breakout_lookback=int(cfg.get("tl_scan_breakout_lookback", 3)),
                touch_tolerance_pct=float(cfg.get("tl_scan_touch_tolerance_pct", 1.5)),
                require_volume=bool(cfg.get("tl_scan_require_volume", True)),
                volume_factor=float(cfg.get("tl_scan_volume_factor", 1.5)),
                min_touches=int(cfg.get("tl_scan_min_touches", 3)),
            )
        elif kind == "triangle":
            out = fetch_and_scan_triangle_only(
                yf_symbol, period, use_cache=bool(cfg.get("use_cache", True)),
                pivot_window=int(cfg.get("tri_scan_pivot_window", 3)),
                min_span_bars=int(cfg.get("tri_scan_min_span_bars", 28)),
                lookback_bars=int(cfg.get("tri_scan_lookback_bars", 200)),
                min_apex_bars_ahead=int(cfg.get("tri_scan_min_apex_bars_ahead", 1)),
                max_apex_bars_ahead=int(cfg.get("tri_scan_max_apex_bars_ahead", 40)),
                max_squeeze_pct=float(cfg.get("tri_scan_max_squeeze_pct", 50.0)),
            )
        elif kind == "combined":
            return result
        else:
            return result
    except Exception as exc:
        repaired = dict(result or {})
        repaired["_chart_repair_error"] = f"Grafik verisi hazırlanamadı: {exc}"
        return repaired

    if out and out.get("matched") and isinstance(out.get("result"), dict):
        rebuilt = out["result"]
        if isinstance(result, dict) and result.get("quality") is not None:
            rebuilt["quality"] = result.get("quality")
        return rebuilt

    repaired = dict(result or {})
    repaired["_chart_repair_error"] = "Bu sonuç güncel veride aynı formasyon şartını artık karşılamıyor. Taramayı yeniden çalıştırın."
    return repaired


def render_quality_panel(result, *, compact=False):
    q = (result or {}).get("quality") or {}
    if not q:
        return
    score = float(q.get("score") or 0)
    rsi = "—" if q.get("rsi14") is None else f"{float(q['rsi14']):.1f}"
    room = "—" if q.get("resistance_room_pct") is None else f"%{float(q['resistance_room_pct']):.1f}"
    if compact:
        st.info(f"Yükseliş Puanı **{score:.1f}/100** · **{q_grade(result)}** · RSI **{rsi}** · Dirence alan **{room}**")
        return
    st.markdown("### Yukarı Yön Kalitesi")
    c1, c2 = st.columns(2)
    c1.metric("Puan", f"{score:.1f}/100")
    c2.metric("Sınıf", q_grade(result))
    c3, c4 = st.columns(2)
    c3.metric("RSI 14", rsi)
    c4.metric("Dirence Alan", room)
    if q.get("reasons"):
        st.success("Güçlü teyitler: " + " · ".join(q["reasons"][:5]))
    if q.get("warnings"):
        st.caption("⚠️ " + " · ".join(q["warnings"][:5]))
    comps = q.get("components") or {}
    if comps:
        st.dataframe(pd.DataFrame([{"Bileşen": k, "Puan": v} for k, v in comps.items()]), width="stretch", hide_index=True)
    st.caption("Bu puan garanti getiri değildir; teknik sinyalleri aynı ölçekte sıralamak için kullanılır.")


def open_chart(kind, sym, result):
    st.session_state["_chart_page"] = {"kind": kind, "symbol": sym, "result": result}
    st.rerun()


def render_chart_page_if_requested():
    view = st.session_state.get("_chart_page")
    if not view:
        return False

    if st.button("← Geri", type="secondary", width="content"):
        st.session_state.pop("_chart_page", None)
        st.session_state["_app_page"] = "Sonuçlar"
        st.rerun()

    kind = view.get("kind")
    sym = view.get("symbol", "")
    result = repair_chart_payload(kind, sym, view.get("result"))
    st.session_state["_chart_page"]["result"] = result
    title_map = {
        "vwap": "VWAP",
        "triangle": "Üçgen",
        "trendline": "Düşen Trend Kırılımı",
        "alternation": "Alternasyon",
    }
    # TradingView benzeri sade grafik ekranı: üstte ekstra puan kartı/başlık yok.
    if kind == "combined":
        active = list(((result or {}).get("signals") or {}).keys())
        if active:
            st.caption("Çizilen sinyaller: " + " + ".join(active))

    if not chart_payload_complete(kind, result):
        st.error((result or {}).get("_chart_repair_error") or "Grafik için gerekli veri bulunamadı. İlgili taramayı yeniden çalıştırın.")
        return True
    try:
        if kind == "vwap":
            render_vwap_chart(sym, result, key=f"chart_vwap_{sym}")
        elif kind == "triangle":
            render_triangle_chart(sym, result, key=f"chart_tri_{sym}")
        elif kind == "trendline":
            render_trendline_chart(sym, result, key=f"chart_tl_{sym}")
        elif kind == "alternation":
            render_alternation_chart(sym, result, key=f"chart_alt_{sym}")
        elif kind == "combined":
            render_combined_chart(sym, result, key=f"chart_combo_{sym}")
    except Exception as exc:
        st.error(f"{sym} grafiği çizilemedi: {exc}")
        st.exception(exc)
        return True

    with st.expander("Puan detayı", expanded=False):
        render_quality_panel(result, compact=False)
    return True


# -----------------------------------------------------------------------------
# Sonuç tablo yardımcıları
# -----------------------------------------------------------------------------
def result_rows(view, items):
    rows = []
    for r in items:
        base = {
            "Sembol": r.get("symbol", "—"),
            "Yükseliş Puanı": round(q_score(r), 1),
            "Kalite": q_grade(r),
            "Teyitler": q_reasons(r),
        }
        if view == "VWAP":
            base.update({
                "Seviye": f"{r.get('level', '—')}. VWAP",
                "Kırılma": r.get("cross_date", "—"),
                "Bar Önce": r.get("bars_ago", "—"),
                "Son Kapanış": r.get("last_close", "—"),
                "VWAP": r.get("last_vwap", "—"),
                "ATH'den Düşüş %": format_drawdown_value(r),
                "Yataylık": format_sideways_status(r),
                "Filtre": "✅ Uygun" if bool(r.get("filter_pass", True)) else "❌ Uygun değil",
            })
        elif view == "Üçgen":
            base.update({
                "Desen": r.get("pattern_type", "—"),
                "Apex Bar": r.get("apex_bars_ahead", "—"),
                "Sıkışma %": r.get("squeeze_pct", "—"),
                "Son Kapanış": r.get("last_close", "—"),
            })
        elif view == "Düşen Trend":
            base.update({
                "Temas": r.get("touches", "—"),
                "Kırılma": r.get("cross_date", "—"),
                "Bar Önce": r.get("bars_ago", "—"),
                "Son Kapanış": r.get("last_close", "—"),
            })
        elif view == "Alternasyon":
            base.update({
                "Zincir": r.get("chain_length", "—"),
                "Alternasyon Desen Puanı": r.get("score", "—"),
                "Gövde Örtüşme %": r.get("mean_body_overlap_pct", "—"),
                "Süreklilik": r.get("continuity_score", "—"),
                "Başlangıç": r.get("start_date", "—"),
                "Bitiş": r.get("end_date", "—"),
            })
        rows.append(base)
    return rows


def chart_kind_for(view):
    return {
        "VWAP": "vwap",
        "Üçgen": "triangle",
        "Düşen Trend": "trendline",
        "Alternasyon": "alternation",
    }[view]


def render_results_page():
    ensure_result_store()
    sets = st.session_state._result_sets
    meta = st.session_state._result_meta

    st.title("Sonuçlar")

    names = ["VWAP", "Üçgen", "Düşen Trend", "Alternasyon"]
    active_job = _resolve_job_snapshot(auto_attach_running=True)
    if not any(sets.get(n) is not None for n in names):
        if active_job and active_job.get("status") in {"queued", "running"}:
            st.warning("Tarama devam ediyor")
        else:
            st.warning("Henüz sonuç yok")
            if st.button("🔎 Tarama sayfasına git", type="primary", width="stretch"):
                set_page("Tarama")
        return

    cfg_ui = load_settings()
    focus = st.session_state.get("_results_focus") or cfg_ui.get("ui_results_view", "Karar Tablosu")
    choices = ["Karar Tablosu", "Özet"] + names + ["Yataylık", "ATH'den Düşüş"]
    if focus not in choices:
        focus = "Karar Tablosu"
    init_widget_state("results_view_select", focus)
    view = st.radio(
        "Bölüm", choices, key="results_view_select", horizontal=True, label_visibility="collapsed",
        format_func=lambda x: {"Karar Tablosu":"Karar", "Düşen Trend":"Trend", "Alternasyon":"Alt", "ATH'den Düşüş":"Düşüş"}.get(x, x),
        on_change=persist_global_widget, args=("ui_results_view", "results_view_select"),
    )
    st.session_state["_results_focus"] = view
    save_partial_settings_if_changed({"ui_results_view": view})

    if view == "Karar Tablosu":
        combined_rows = build_combined_analysis(sets)
        if not combined_rows:
            st.warning("Birleştirilecek sonuç bulunamadı.")
            return

        render_result_stats(combined_rows)

        decision_defaults = {
            "query": get_result_pref("Karar Tablosu", "query", ""),
            "min_signal": get_result_pref("Karar Tablosu", "min_signal", 1),
            "min_score": get_result_pref("Karar Tablosu", "min_score", 0),
            "required_signals": get_result_pref("Karar Tablosu", "required_signals", []),
            "sort": get_result_pref("Karar Tablosu", "sort", "Sinyal Sayısı ↓"),
        }
        init_widget_state("decision_symbol_search", decision_defaults["query"])
        init_widget_state("decision_min_signal", decision_defaults["min_signal"])
        init_widget_state("decision_min_score", decision_defaults["min_score"])
        init_widget_state("decision_required_signals", decision_defaults["required_signals"])
        init_widget_state("decision_sort_mode", decision_defaults["sort"])

        f1, f2, f3, f4, f5 = st.columns([1.25, .8, .8, 1.25, 1.15])
        with f1:
            query = st.text_input("Hisse", placeholder="THYAO", key="decision_symbol_search", on_change=persist_result_widget, args=("Karar Tablosu", "query", "decision_symbol_search"))
        with f2:
            min_signal = st.selectbox("Min. sinyal", [1, 2, 3, 4], key="decision_min_signal", on_change=persist_result_widget, args=("Karar Tablosu", "min_signal", "decision_min_signal"))
        with f3:
            min_score = st.selectbox("Min. puan", [0, 50, 60, 70, 80], key="decision_min_score", on_change=persist_result_widget, args=("Karar Tablosu", "min_score", "decision_min_score"))
        with f4:
            required_signals = st.multiselect("Sinyal", ["VWAP", "Üçgen", "Düşen Trend", "Alternasyon"], key="decision_required_signals", placeholder="Tümü", on_change=persist_result_widget, args=("Karar Tablosu", "required_signals", "decision_required_signals"))
        with f5:
            sort_mode = st.selectbox("Sırala", ["Sinyal Sayısı ↓", "En Yüksek Puan ↓", "Ortalama Puan ↓", "RSI 14 ↓", "Hacim Oranı ↓", "ATH / Anchor Düşüş ↓", "Sembol A-Z"], key="decision_sort_mode", on_change=persist_result_widget, args=("Karar Tablosu", "sort", "decision_sort_mode"))

        # Mobilde filtreyi değiştirip hemen karta dokunulsa bile son değerleri kalıcılaştır.
        save_result_pref("Karar Tablosu", "query", query)
        save_result_pref("Karar Tablosu", "min_signal", min_signal)
        save_result_pref("Karar Tablosu", "min_score", min_score)
        save_result_pref("Karar Tablosu", "required_signals", list(required_signals or []))
        save_result_pref("Karar Tablosu", "sort", sort_mode)

        filtered = []
        qtxt = str(query or "").strip().upper()
        for row in combined_rows:
            if qtxt and qtxt not in str(row.get("Sembol", "")).upper():
                continue
            if int(row.get("Sinyal Sayısı") or 0) < int(min_signal):
                continue
            if float(row.get("En Yüksek Puan") or 0) < float(min_score):
                continue
            if required_signals:
                row_signals = set((row.get("_signal_results") or {}).keys())
                if not all(sig in row_signals for sig in required_signals):
                    continue
            filtered.append(row)
        filtered = sort_combined_rows(filtered, sort_mode)

        render_decision_cards(filtered)
        with st.expander("CSV", expanded=False):
            export_df = pd.DataFrame(filtered).drop(columns=[c for c in pd.DataFrame(filtered).columns if str(c).startswith("_")], errors="ignore")
            st.download_button("CSV İndir", export_df.to_csv(index=False).encode("utf-8-sig"), file_name="bist_karar_tablosu.csv", mime="text/csv", width="stretch")
        return

    if view == "Özet":
        combined = []
        for name in names:
            for r in list(sets.get(name) or []):
                combined.append((q_score(r), name, r))
        combined.sort(key=lambda x: x[0], reverse=True)
        if not combined:
            st.warning("Kayıtlı sonuçların içinde eşleşme yok.")
            return
        overview_items = combined[:50]
        overview_df = pd.DataFrame([
            {
                "Sembol": str(r.get("symbol", "—")).replace(".IS", ""),
                "Tarama": (f"VWAP · {r.get('level', '—')}. VWAP" if name == "VWAP" else name),
                "Puan": round(q_score(r), 1),
                "Kalite": q_grade(r),
                "Teyit": q_reasons(r),
            }
            for _, name, r in overview_items
        ])
        overview_results = [r for _, _, r in overview_items]
        render_simple_signal_cards("Özet", overview_results)
        return

    items = list(sets.get(view) or [])
    m = meta.get(view) or {}
    errors = list(m.get("errors") or [])

    if view in {"Yataylık", "ATH'den Düşüş"}:
        st.caption(f"Periyot: **{m.get('period') or 'Günlük yardımcı hesap'}** · Taranan: **{m.get('total') or '—'}** · Tarama: **{m.get('scan_time') or '—'}**")
        if not items:
            st.warning("Bu yardımcı filtre için eşleşme bulunamadı.")
            return
        if view == "Yataylık":
            rows = [{
                "Sembol": r.get("symbol", "—"),
                "Yatay": "✅ Evet",
                "Vade": f"{r.get('sideways_count', 0)}/{r.get('total_windows', 0)}",
                "Aylar": ", ".join(str(x) for x in (r.get("sideways_months") or [])) or "—",
                "Anchor": r.get("anchor_reason") or "—",
                "Tarih": r.get("anchor_date") or "—",
            } for r in items]
        else:
            rows = [{
                "Sembol": r.get("symbol", "—"),
                "Düşüş %": r.get("drawdown_pct", "—"),
                "Anchor": r.get("anchor_reason") or "—",
                "Tarih": r.get("anchor_date") or "—",
            } for r in sorted(items, key=lambda z: float(z.get("drawdown_pct") or 0), reverse=True)]
        helper_df = pd.DataFrame(rows)
        for idx, row in enumerate(rows):
            sym = str(row.get("Sembol") or "—").replace(".IS", "")
            signals = collect_signal_results_for_symbol(sets, sym)
            with st.container(border=True):
                if st.button(sym, key=f"helper_open_{view}_{sym}_{idx}", width="stretch", type="secondary", disabled=not bool(signals)):
                    if len(signals) >= 2:
                        open_chart("combined", sym, build_combined_chart_payload(sym, signals))
                    elif signals:
                        name, result = next(iter(signals.items()))
                        open_chart(chart_kind_for(name), sym, result)
                chips = ''.join(f'<span class="src-chip">{html.escape(str(k))}: {html.escape(_fmt_cell(v))}</span>' for k, v in row.items() if k != "Sembol")
                st.markdown(f'<div class="src-body">{chips}</div>', unsafe_allow_html=True)
        with st.expander("CSV", expanded=False):
            st.download_button("CSV İndir", helper_df.to_csv(index=False).encode("utf-8-sig"), file_name=("yataylik_sonuclari.csv" if view == "Yataylık" else "ath_dusus_sonuclari.csv"), mime="text/csv", width="stretch")
        return

    if view == "VWAP":
        fs = m.get("filters") or {}
        filters_active = bool(fs.get("sideways_enabled") or fs.get("drawdown_enabled"))
        if filters_active:
            pass_count = sum(1 for r in items if bool((r or {}).get("filter_pass", True)))
            scope_mode = get_result_pref("VWAP", "scope", "Tüm")
            scope_options = [f"Tüm VWAP'lar ({len(items)})", f"Filtreye Uyanlar ({pass_count})"]
            scope_default = scope_options[1] if scope_mode == "Filtre" else scope_options[0]
            init_widget_state("vwap_filter_scope", scope_default)
            scope = st.radio("VWAP görünümü", scope_options, horizontal=True, key="vwap_filter_scope")
            scope_mode_now = "Filtre" if scope.startswith("Filtreye Uyanlar") else "Tüm"
            save_result_pref("VWAP", "scope", scope_mode_now)
            if scope_mode_now == "Filtre":
                items = [r for r in items if bool((r or {}).get("filter_pass", True))]
        level_counts = {level: sum(1 for r in items if int(r.get("level") or 0) == level) for level in (1, 2, 3)}
        level_options = [f"Tümü ({len(items)})", f"1. VWAP ({level_counts[1]})", f"2. VWAP ({level_counts[2]})", f"3. VWAP ({level_counts[3]})"]
        saved_level = int(get_result_pref("VWAP", "level", 0) or 0)
        level_default = next((x for x in level_options if (saved_level == 0 and x.startswith("Tümü")) or (saved_level and x.startswith(f"{saved_level}. VWAP"))), level_options[0])
        init_widget_state("vwap_level_filter", level_default)
        level_choice = st.radio("VWAP seviyesi", level_options, horizontal=True, key="vwap_level_filter")
        selected_level = 0 if level_choice.startswith("Tümü") else int(level_choice.split(".", 1)[0])
        save_result_pref("VWAP", "level", selected_level)
        if selected_level:
            items = [r for r in items if int(r.get("level") or 0) == selected_level]

    st.caption(f"{m.get('period') or '—'} · {m.get('total') or '—'} hisse · {len(errors)} hata")

    quality_key = f"quality_{view}"
    search_key = f"search_{view}"
    sort_key = f"sort_{view}"
    init_widget_state(quality_key, get_result_pref(view, "quality", "Tümü"))
    init_widget_state(search_key, get_result_pref(view, "search", ""))
    sort_options = {
        "VWAP": ["Yükseliş Puanı ↓", "VWAP Seviyesi ↓", "Bar Önce ↑", "ATH / Anchor Düşüş ↓", "Sembol A-Z"],
        "Üçgen": ["Yükseliş Puanı ↓", "Sıkışma % ↑", "Sembol A-Z"],
        "Düşen Trend": ["Yükseliş Puanı ↓", "Temas ↓", "Bar Önce ↑", "Sembol A-Z"],
        "Alternasyon": ["Yükseliş Puanı ↓", "Desen Puanı ↓", "Zincir ↓", "Sembol A-Z"],
    }
    saved_sort = get_result_pref(view, "sort", "Yükseliş Puanı ↓")
    if saved_sort not in sort_options.get(view, []):
        saved_sort = sort_options.get(view, ["Yükseliş Puanı ↓"])[0]
    init_widget_state(sort_key, saved_sort)
    f1, f2, f3 = st.columns(3)
    with f1:
        min_quality_label = st.selectbox("En düşük kalite", ["Tümü", "60+", "70+", "80+"], key=quality_key, on_change=persist_result_widget, args=(view, "quality", quality_key))
    with f2:
        search = st.text_input("Hisse ara", placeholder="Örn: THYAO", key=search_key, on_change=persist_result_widget, args=(view, "search", search_key))
    with f3:
        sort_mode = st.selectbox("Sırala", sort_options.get(view, ["Yükseliş Puanı ↓", "Sembol A-Z"]), key=sort_key, on_change=persist_result_widget, args=(view, "sort", sort_key))
    save_result_pref(view, "quality", min_quality_label)
    save_result_pref(view, "search", search)
    save_result_pref(view, "sort", sort_mode)
    min_score = {"Tümü": 0, "60+": 60, "70+": 70, "80+": 80}[min_quality_label]
    filtered = [r for r in items if q_score(r) >= min_score]
    if search.strip():
        needle = search.strip().upper()
        filtered = [r for r in filtered if needle in str(r.get("symbol", "")).upper()]
    filtered = sort_view_rows(view, filtered, sort_mode)
    if not filtered:
        st.warning("Bu filtreye uyan sonuç yok.")
        return

    render_simple_signal_cards(view, filtered)
    df = pd.DataFrame(result_rows(view, filtered))
    with st.expander("CSV", expanded=False):
        st.download_button("CSV İndir", df.to_csv(index=False).encode("utf-8-sig"), file_name=f"{view.lower().replace(' ', '_')}_sonuclar.csv", mime="text/csv", width="stretch")
    if errors:
        with st.expander(f"Veri hataları ({len(errors)})"):
            for item in errors[:50]:
                sym, err = normalize_error_entry(item)
                st.code(f"{sym}: {err}")


# -----------------------------------------------------------------------------
# Tarama çalıştırıcıları


# -----------------------------------------------------------------------------
def make_progress_callback(progress, label, start=0.0, span=1.0):
    def cb(done, total, sym):
        ratio = (done / total) if total else 1.0
        progress.progress(min(1.0, start + span * ratio), text=f"{label}: {done}/{total} · {sym}")
    return cb


def run_vwap_scan(symbols, cfg, progress=None, start=0.0, span=1.0, source="VWAP taraması"):
    errors = []
    callback = make_progress_callback(progress, "VWAP taranıyor", start, span) if progress is not None else None
    results, _, _, _, _, _ = scan_symbols_parallel(
        symbols,
        cfg.get("period", "weekly"),
        lookback=int(cfg.get("lookback", 3)),
        max_workers=int(cfg.get("max_workers", 20)),
        use_cache=bool(cfg.get("use_cache", True)),
        progress_callback=callback,
        errors_out=errors,
        sideways_enabled=bool(cfg.get("sideways_enabled", False)),
        sideways_months_list=list(cfg.get("sideways_months_list") or [12, 18, 24]),
        sideways_range_pct=float(cfg.get("sideways_range_pct", 15.0)),
        sideways_atr_pct=float(cfg.get("sideways_atr_pct", 5.0)),
        sideways_method=str(cfg.get("sideways_method", "atr")),
        sideways_min_windows=cfg.get("sideways_min_windows"),
        drawdown_enabled=bool(cfg.get("drawdown_enabled", False)),
        drawdown_min_pct=float(cfg.get("drawdown_min_pct", 50.0)),
        alternation_enabled=False,
        trendline_enabled=False,
        triangle_enabled=False,
        currency=str(cfg.get("currency", "TRY")),
    )
    results = [enrich_actual_ath_drawdown(r, cfg.get("drawdown_min_pct", 50.0)) for r in results]
    raw_count = len(results)
    results = [r for r in results if vwap_filter_passes(r, cfg)]
    store_result_set(
        "VWAP", results, total=len(symbols), period=PERIOD_LABELS.get(cfg.get("period"), cfg.get("period")),
        errors=errors, source=source, currency=cfg.get("currency"),
        meta_extra={
            "before_filter_count": raw_count,
            "filters": {
                "sideways_enabled": bool(cfg.get("sideways_enabled", False)),
                "sideways_months": list(cfg.get("sideways_months_list") or [12, 18, 24]),
                "sideways_method": str(cfg.get("sideways_method", "atr")),
                "sideways_range_pct": float(cfg.get("sideways_range_pct", 15.0)),
                "sideways_atr_pct": float(cfg.get("sideways_atr_pct", 5.0)),
                "drawdown_enabled": bool(cfg.get("drawdown_enabled", False)),
                "drawdown_min_pct": float(cfg.get("drawdown_min_pct", 50.0)),
            },
        },
    )
    return results, errors


def run_triangle_scan(symbols, cfg, progress=None, start=0.0, span=1.0, source="Üçgen taraması"):
    errors = []
    callback = make_progress_callback(progress, "Üçgen taranıyor", start, span) if progress is not None else None
    results = scan_triangle_symbols_parallel(
        symbols, cfg.get("tri_scan_period", "4h"),
        max_workers=int(cfg.get("max_workers", 20)), use_cache=bool(cfg.get("use_cache", True)),
        progress_callback=callback, errors_out=errors,
        pivot_window=int(cfg.get("tri_scan_pivot_window", 3)),
        min_span_bars=int(cfg.get("tri_scan_min_span_bars", 28)),
        lookback_bars=int(cfg.get("tri_scan_lookback_bars", 200)),
        min_apex_bars_ahead=int(cfg.get("tri_scan_min_apex_bars_ahead", 1)),
        max_apex_bars_ahead=int(cfg.get("tri_scan_max_apex_bars_ahead", 40)),
        max_squeeze_pct=float(cfg.get("tri_scan_max_squeeze_pct", 50.0)),
    )
    store_result_set(
        "Üçgen", results, total=len(symbols),
        period=TRIANGLE_SCAN_PERIOD_LABELS.get(cfg.get("tri_scan_period"), cfg.get("tri_scan_period")),
        errors=errors, source=source,
    )
    return results, errors


def run_trend_scan(symbols, cfg, progress=None, start=0.0, span=1.0, source="Düşen trend taraması"):
    errors = []
    callback = make_progress_callback(progress, "Düşen trend taranıyor", start, span) if progress is not None else None
    results = scan_trendline_symbols_parallel(
        symbols, cfg.get("tl_scan_period", "1h"),
        max_workers=int(cfg.get("max_workers", 20)), use_cache=bool(cfg.get("use_cache", True)),
        progress_callback=callback, errors_out=errors,
        pivot_window=int(cfg.get("tl_scan_pivot_window", 3)),
        min_span_bars=int(cfg.get("tl_scan_min_span_bars", 30)),
        lookback_bars=int(cfg.get("tl_scan_lookback_bars", 200)),
        breakout_lookback=int(cfg.get("tl_scan_breakout_lookback", 3)),
        touch_tolerance_pct=float(cfg.get("tl_scan_touch_tolerance_pct", 1.5)),
        require_volume=bool(cfg.get("tl_scan_require_volume", True)),
        volume_factor=float(cfg.get("tl_scan_volume_factor", 1.5)),
        min_touches=int(cfg.get("tl_scan_min_touches", 3)),
    )
    store_result_set(
        "Düşen Trend", results, total=len(symbols),
        period=TRENDLINE_SCAN_PERIOD_LABELS.get(cfg.get("tl_scan_period"), cfg.get("tl_scan_period")),
        errors=errors, source=source,
    )
    return results, errors


def run_alternation_scan(symbols, cfg, progress=None, start=0.0, span=1.0, source="Alternasyon taraması"):
    errors = []
    callback = make_progress_callback(progress, "Alternasyon taranıyor", start, span) if progress is not None else None
    min_score = cfg.get("alt_scan_min_score")
    if min_score in ("", None):
        min_score = None
    else:
        min_score = float(min_score)
    results = scan_alternation_symbols_parallel(
        symbols, cfg.get("alt_scan_period", "monthly"),
        max_workers=int(cfg.get("max_workers", 20)), use_cache=bool(cfg.get("use_cache", True)),
        progress_callback=callback, errors_out=errors,
        min_chain=int(cfg.get("alt_scan_min_chain", 3)), min_score=min_score,
    )
    store_result_set(
        "Alternasyon", results, total=len(symbols),
        period=ALTERNATION_SCAN_PERIOD_LABELS.get(cfg.get("alt_scan_period"), cfg.get("alt_scan_period")),
        errors=errors, source=source,
    )
    return results, errors


# -----------------------------------------------------------------------------
# Ana sayfa
# -----------------------------------------------------------------------------
def render_home():
    ensure_result_store()
    sets = st.session_state._result_sets

    st.markdown(
        """
<div class="hero">
  <h2 style="margin:0;">BIST Tarama</h2>
  <div class="small-muted">Sade kullanım: Tara · Sonuçlar · Grafik</div>
</div>
""",
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    for col, name in zip(cols, ["VWAP", "Üçgen", "Düşen Trend", "Alternasyon"]):
        rows = list(sets.get(name) or [])
        col.metric(name, len(rows))

    st.markdown("### Hızlı Başlat")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📍 VWAP", type="primary", width="stretch"):
            set_page("Tarama", "VWAP")
    with c2:
        if st.button("🔺 Üçgen", width="stretch"):
            set_page("Tarama", "Üçgen")
    c3, c4 = st.columns(2)
    with c3:
        if st.button("📉 Düşen Trend", width="stretch"):
            set_page("Tarama", "Düşen Trend")
    with c4:
        if st.button("🔀 Alternasyon", width="stretch"):
            set_page("Tarama", "Alternasyon")

    c5, c6 = st.columns(2)
    with c5:
        if st.button("🚀 Tümünü Tara", type="primary", width="stretch"):
            set_page("Tarama", "Tümünü Tara")
    with c6:
        if st.button("📊 Sonuçlar", width="stretch"):
            set_page("Sonuçlar", result_focus="Karar Tablosu")


# -----------------------------------------------------------------------------
# Tarama sayfası
# -----------------------------------------------------------------------------
def render_scan_page():
    cfg = load_settings()
    st.title("Tarama")

    # Hisse listesi ve çalışma ayarları tek yerde, varsayılan kapalı.
    current_text = symbol_text_from_settings(cfg)
    symbols_now = normalize_symbol_list([current_text])
    with st.expander(f"📋 Hisse Listesi ve Genel Ayarlar · {len(symbols_now)} hisse", expanded=False):
        manual_text = st.text_area(
            "Taranacak hisseler",
            value=current_text,
            height=180,
            help="Satır satır veya virgülle yazabilirsiniz. .IS yazmasanız da sistem ekler.",
            key="symbol_list_text",
        )
        symbols = normalize_symbol_list([manual_text])
        st.caption(f"Aktif liste: **{len(symbols)} hisse**")
        g1, g2 = st.columns(2)
        with g1:
            max_workers = st.slider("Tarama hızı / eşzamanlı iş (1s/4s Yahoo taramalarında otomatik en fazla 6)", 4, 40, int(cfg.get("max_workers", 20)), 2, key="general_workers")
        with g2:
            use_cache = st.checkbox("Önbelleği kullan (önerilir)", value=bool(cfg.get("use_cache", True)), key="general_cache")
        def _reload_bist_list():
            st.session_state["symbol_list_text"] = read_bist_list_text()

        st.button(
            "BIST listesini dosyadan yeniden yükle",
            width="stretch",
            on_click=_reload_bist_list,
        )
    # Expander içindeki widgetlar ilk renderda da değer üretir.
    manual_text = st.session_state.get("symbol_list_text", current_text)
    symbols = normalize_symbol_list([manual_text])
    max_workers = int(st.session_state.get("general_workers", cfg.get("max_workers", 20)))
    use_cache = bool(st.session_state.get("general_cache", cfg.get("use_cache", True)))
    save_partial_settings({"son_semboller_text": manual_text, "max_workers": max_workers, "use_cache": use_cache})

    scan_choices = ["VWAP", "Üçgen", "Düşen Trend", "Alternasyon", "Tümünü Tara"]
    saved_choice = st.session_state.get("_scan_type") or cfg.get("last_scan_type", "VWAP")
    if saved_choice not in scan_choices:
        saved_choice = "VWAP"
    init_widget_state("scan_type_select", saved_choice)
    selected = st.radio("Tarama Türü", scan_choices, key="scan_type_select", horizontal=True, label_visibility="collapsed", on_change=persist_global_widget, args=("last_scan_type", "scan_type_select"))
    st.session_state["_scan_type"] = selected
    save_partial_settings_if_changed({"last_scan_type": selected})

    if not symbols:
        st.error("Taranacak hisse listesi boş. 'Hisse Listesi ve Genel Ayarlar' bölümünden hisse ekleyin.")
        return

    # Her taramada sadece gerekli ayarlar görünür.
    if selected == "VWAP":
        st.markdown("### 📍 VWAP")
        c1, c2, c3 = st.columns(3)
        with c1:
            period = st.selectbox(
                "Periyot", list(PERIOD_OPTIONS),
                index=list(PERIOD_OPTIONS).index(cfg.get("period", "weekly")) if cfg.get("period") in PERIOD_OPTIONS else 1,
                format_func=lambda p: PERIOD_LABELS.get(p, p), key="vwap_period",
            )
        with c2:
            currency = st.selectbox(
                "Para birimi", list(CURRENCY_OPTIONS),
                index=list(CURRENCY_OPTIONS).index(cfg.get("currency", "TRY")) if cfg.get("currency") in CURRENCY_OPTIONS else 0,
                format_func=lambda x: CURRENCY_LABELS.get(x, x), key="vwap_currency",
            )
        with c3:
            lookback = st.slider("Kırılım son kaç barda olsun?", 1, 8, int(cfg.get("lookback", 3)), key="vwap_lookback")

        with st.expander("⚙️ Gelişmiş VWAP", expanded=False):
            sideways_enabled = st.checkbox("Yataylık filtresini uygula", value=bool(cfg.get("sideways_enabled", False)), key="vwap_sideways")
            sideways_method = cfg.get("sideways_method", "range")
            sideways_months = list(cfg.get("sideways_months_list") or [12, 18, 24])
            sideways_range = float(cfg.get("sideways_range_pct", 15.0))
            sideways_atr = float(cfg.get("sideways_atr_pct", 5.0))
            if sideways_enabled:
                a1, a2 = st.columns(2)
                with a1:
                    sideways_method = st.selectbox("Yataylık yöntemi", ["atr", "range", "both"], index=0 if sideways_method == "atr" else (1 if sideways_method == "range" else 2), format_func=lambda x: {"atr":"ATR", "range":"Fiyat Aralığı", "both":"ATR + Fiyat Aralığı"}[x], key="vwap_sideways_method")
                    sideways_months = st.multiselect("Vadeler (ay)", [3, 6, 12, 18, 24], default=sideways_months, key="vwap_sideways_months")
                with a2:
                    sideways_range = st.slider("Maks. fiyat aralığı %", 5.0, 50.0, sideways_range, 1.0, key="vwap_sideways_range")
                    sideways_atr = st.slider("Maks. ATR %", 1.0, 15.0, sideways_atr, .5, key="vwap_sideways_atr")
            drawdown_enabled = st.checkbox("ATH’den düşüş filtresini uygula", value=bool(cfg.get("drawdown_enabled", False)), key="vwap_drawdown")
            drawdown_min = float(cfg.get("drawdown_min_pct", 50.0))
            if drawdown_enabled:
                drawdown_min = st.slider("En az ATH’den düşüş %", 10.0, 90.0, drawdown_min, 5.0, key="vwap_drawdown_min")
            if sideways_enabled or drawdown_enabled:
                active_parts = []
                if sideways_enabled:
                    active_parts.append("Yataylık şartını geçmeyen VWAP sonuçları elenir")
                if drawdown_enabled:
                    active_parts.append(f"ATH’den en az %{drawdown_min:.0f} düşmeyen VWAP sonuçları elenir")
                st.info("AKTİF FİLTRE: " + " · ".join(active_parts))

        save_partial_settings({
            "period": period, "currency": currency, "lookback": lookback,
            "sideways_enabled": sideways_enabled, "sideways_method": sideways_method,
            "sideways_months_list": sideways_months, "sideways_range_pct": sideways_range,
            "sideways_atr_pct": sideways_atr, "drawdown_enabled": drawdown_enabled,
            "drawdown_min_pct": drawdown_min,
        })
        cfg = load_settings()
        if st.button(f"🔍 VWAP Tara · {len(symbols)} hisse", type="primary", width="stretch"):
            launch_background_scan("VWAP", symbols, cfg, result_focus="VWAP")

    elif selected == "Üçgen":
        st.markdown("### 🔺 Üçgen Taraması")
        st.caption("Sıkışmış, apex'e yaklaşmış ve kırılıma hazır üçgenleri arar.")
        tri_period = st.selectbox(
            "Periyot", list(TRIANGLE_SCAN_PERIOD_OPTIONS),
            index=list(TRIANGLE_SCAN_PERIOD_OPTIONS).index(cfg.get("tri_scan_period", "4h")) if cfg.get("tri_scan_period") in TRIANGLE_SCAN_PERIOD_OPTIONS else 1,
            format_func=lambda p: TRIANGLE_SCAN_PERIOD_LABELS.get(p, p), key="tri_period",
        )
        tri_vals = {
            "tri_scan_pivot_window": int(cfg.get("tri_scan_pivot_window", 3)),
            "tri_scan_min_span_bars": int(cfg.get("tri_scan_min_span_bars", 28)),
            "tri_scan_lookback_bars": int(cfg.get("tri_scan_lookback_bars", 200)),
            "tri_scan_min_apex_bars_ahead": int(cfg.get("tri_scan_min_apex_bars_ahead", 1)),
            "tri_scan_max_apex_bars_ahead": int(cfg.get("tri_scan_max_apex_bars_ahead", 40)),
            "tri_scan_max_squeeze_pct": float(cfg.get("tri_scan_max_squeeze_pct", 50.0)),
        }
        with st.expander("⚙️ Gelişmiş üçgen ayarları", expanded=False):
            a1, a2 = st.columns(2)
            with a1:
                tri_vals["tri_scan_pivot_window"] = st.slider("Pivot penceresi", 2, 8, tri_vals["tri_scan_pivot_window"], key="tri_pivot")
                tri_vals["tri_scan_min_span_bars"] = st.slider("Min. çizgi uzunluğu (bar)", 5, 60, tri_vals["tri_scan_min_span_bars"], key="tri_span")
                tri_vals["tri_scan_lookback_bars"] = st.slider("Geçmiş arama (bar)", 40, 500, tri_vals["tri_scan_lookback_bars"], key="tri_lookback")
            with a2:
                tri_vals["tri_scan_min_apex_bars_ahead"] = st.slider("Apex en az kaç bar sonra?", 1, 20, tri_vals["tri_scan_min_apex_bars_ahead"], key="tri_apex_min")
                tri_vals["tri_scan_max_apex_bars_ahead"] = st.slider("Apex en fazla kaç bar sonra?", 5, 100, tri_vals["tri_scan_max_apex_bars_ahead"], key="tri_apex_max")
                tri_vals["tri_scan_max_squeeze_pct"] = st.slider("Maks. sıkışma %", 10.0, 90.0, tri_vals["tri_scan_max_squeeze_pct"], 5.0, key="tri_squeeze")
        save_partial_settings({"tri_scan_period": tri_period, **tri_vals})
        cfg = load_settings()
        if st.button(f"🔍 Üçgen Tara · {len(symbols)} hisse", type="primary", width="stretch"):
            launch_background_scan("Üçgen", symbols, cfg, result_focus="Üçgen")

    elif selected == "Düşen Trend":
        st.markdown("### 📉 Düşen Trend Kırılımı")
        st.caption("Düşen direnç çizgisini yukarı kıran ve kırılımı koruyan hisseleri arar.")
        c1, c2 = st.columns(2)
        with c1:
            tl_period = st.selectbox(
                "Periyot", list(TRENDLINE_SCAN_PERIOD_OPTIONS),
                index=list(TRENDLINE_SCAN_PERIOD_OPTIONS).index(cfg.get("tl_scan_period", "1h")) if cfg.get("tl_scan_period") in TRENDLINE_SCAN_PERIOD_OPTIONS else 0,
                format_func=lambda p: TRENDLINE_SCAN_PERIOD_LABELS.get(p, p), key="tl_period",
            )
        with c2:
            tl_volume = st.checkbox("Hacim teyidi şart olsun", value=bool(cfg.get("tl_scan_require_volume", True)), key="tl_volume")
        tl_vals = {
            "tl_scan_pivot_window": int(cfg.get("tl_scan_pivot_window", 3)),
            "tl_scan_min_span_bars": int(cfg.get("tl_scan_min_span_bars", 30)),
            "tl_scan_lookback_bars": int(cfg.get("tl_scan_lookback_bars", 200)),
            "tl_scan_breakout_lookback": int(cfg.get("tl_scan_breakout_lookback", 3)),
            "tl_scan_touch_tolerance_pct": float(cfg.get("tl_scan_touch_tolerance_pct", 1.5)),
            "tl_scan_min_touches": int(cfg.get("tl_scan_min_touches", 3)),
            "tl_scan_volume_factor": float(cfg.get("tl_scan_volume_factor", 1.5)),
        }
        with st.expander("⚙️ Gelişmiş düşen trend ayarları", expanded=False):
            a1, a2 = st.columns(2)
            with a1:
                tl_vals["tl_scan_pivot_window"] = st.slider("Pivot penceresi", 2, 8, tl_vals["tl_scan_pivot_window"], key="tl_pivot")
                tl_vals["tl_scan_min_span_bars"] = st.slider("Min. çizgi uzunluğu (bar)", 5, 80, tl_vals["tl_scan_min_span_bars"], key="tl_span")
                tl_vals["tl_scan_lookback_bars"] = st.slider("Geçmiş arama (bar)", 40, 500, tl_vals["tl_scan_lookback_bars"], key="tl_lookback")
                tl_vals["tl_scan_breakout_lookback"] = st.slider("Kırılım son kaç barda?", 1, 10, tl_vals["tl_scan_breakout_lookback"], key="tl_breaklook")
            with a2:
                tl_vals["tl_scan_touch_tolerance_pct"] = st.slider("Temas toleransı %", .5, 5.0, tl_vals["tl_scan_touch_tolerance_pct"], .5, key="tl_tol")
                tl_vals["tl_scan_min_touches"] = st.slider("En az bağımsız temas", 2, 6, tl_vals["tl_scan_min_touches"], key="tl_touches")
                if tl_volume:
                    tl_vals["tl_scan_volume_factor"] = st.slider("Kırılım hacmi / 20 bar ort.", 1.0, 5.0, tl_vals["tl_scan_volume_factor"], .1, key="tl_vol_factor")
        save_partial_settings({"tl_scan_period": tl_period, "tl_scan_require_volume": tl_volume, **tl_vals})
        cfg = load_settings()
        if st.button(f"🔍 Düşen Trend Tara · {len(symbols)} hisse", type="primary", width="stretch"):
            launch_background_scan("Düşen Trend", symbols, cfg, result_focus="Düşen Trend")

    elif selected == "Alternasyon":
        st.markdown("### 🔀 Alternasyon Taraması")
        st.caption("Kesintisiz mum renk alternasyonu arar; yukarı yön kalite puanı ile güçlü adayları üstte sıralar.")
        c1, c2, c3 = st.columns(3)
        with c1:
            alt_period = st.selectbox(
                "Periyot", list(ALTERNATION_SCAN_PERIOD_OPTIONS),
                index=list(ALTERNATION_SCAN_PERIOD_OPTIONS).index(cfg.get("alt_scan_period", "monthly")) if cfg.get("alt_scan_period") in ALTERNATION_SCAN_PERIOD_OPTIONS else 4,
                format_func=lambda p: ALTERNATION_SCAN_PERIOD_LABELS.get(p, p), key="alt_period",
            )
        with c2:
            alt_chain = st.slider("En az zincir", 3, 12, int(cfg.get("alt_scan_min_chain", 3)), key="alt_chain")
        with c3:
            alt_score = st.slider("Min. düzenlilik puanı", 0, 100, int(float(cfg.get("alt_scan_min_score") or 0)), 5, key="alt_score")
        save_partial_settings({"alt_scan_period": alt_period, "alt_scan_min_chain": alt_chain, "alt_scan_min_score": None if alt_score == 0 else alt_score})
        cfg = load_settings()
        if st.button(f"🔍 Alternasyon Tara · {len(symbols)} hisse", type="primary", width="stretch"):
            launch_background_scan("Alternasyon", symbols, cfg, result_focus="Alternasyon")

    else:  # Tümünü Tara
        st.markdown("### 🚀 Tümünü Birlikte Tara")
        st.caption("Dört taramayı kendi kayıtlı periyot ve ayarlarıyla sırayla çalıştırır. Bittiğinde tek Sonuçlar ekranına geçer.")
        summary_df = pd.DataFrame([
            {"Tarama": "VWAP", "Periyot": PERIOD_LABELS.get(cfg.get("period"), cfg.get("period")), "Ana Ayar": f"{cfg.get('currency','TRY')} · son {cfg.get('lookback',3)} bar"},
            {"Tarama": "Üçgen", "Periyot": TRIANGLE_SCAN_PERIOD_LABELS.get(cfg.get("tri_scan_period"), cfg.get("tri_scan_period")), "Ana Ayar": f"Sıkışma ≤ %{cfg.get('tri_scan_max_squeeze_pct',50)}"},
            {"Tarama": "Düşen Trend", "Periyot": TRENDLINE_SCAN_PERIOD_LABELS.get(cfg.get("tl_scan_period"), cfg.get("tl_scan_period")), "Ana Ayar": "Hacim teyitli" if cfg.get("tl_scan_require_volume") else "Hacim şart değil"},
            {"Tarama": "Alternasyon", "Periyot": ALTERNATION_SCAN_PERIOD_LABELS.get(cfg.get("alt_scan_period"), cfg.get("alt_scan_period")), "Ana Ayar": f"Min. zincir {cfg.get('alt_scan_min_chain',3)}"},
        ])
        st.dataframe(summary_df, width="stretch", hide_index=True)
        if st.button(f"🚀 Dördünü Tara · {len(symbols)} hisse", type="primary", width="stretch"):
            launch_background_scan("Tümünü Tara", symbols, cfg, result_focus="Karar Tablosu")

    # Normal tarama ayarları bağlıysa değişiklikleri merkezi GitHub variable'a sessizce eşitle.
    sync_linked_auto_scanner_settings(load_settings(), quiet=True)

    st.markdown("---")
    render_auto_scan_settings_panel()
    with st.expander("⚙️ Ayar Yönetimi", expanded=False):
        st.caption("Tarama ayarları ve Sonuçlar ekranındaki filtre/sıralamalar otomatik kaydedilir.")
        confirm_key = "reset_settings_confirm"
        init_widget_state(confirm_key, False)
        confirmed = st.checkbox("Tüm kayıtlı ayarları varsayılana döndür", key=confirm_key)
        if st.button("Tüm Ayarları Sıfırla", type="secondary", width="stretch", disabled=not confirmed, key="reset_settings_button"):
            reset_all_settings()


# -----------------------------------------------------------------------------
# Üst navigasyon ve uygulama yönlendirmesi
# -----------------------------------------------------------------------------
hydrate_site_scanner_settings_from_remote()
_startup_cfg = load_settings()
st.session_state.setdefault("_app_page", "Ana Sayfa")
st.session_state.setdefault("_scan_type", _startup_cfg.get("last_scan_type", "VWAP"))
st.session_state.setdefault("_results_focus", _startup_cfg.get("ui_results_view", "Karar Tablosu"))
st.session_state.setdefault("_active_job_id", None)
st.session_state.setdefault("_synced_job_revision", -1)
ensure_result_store()
_resolve_job_snapshot(auto_attach_running=True)
restore_latest_results_if_needed()
try:
    if st.query_params.get("open") is not None:
        del st.query_params["open"]
except Exception:
    pass

if render_chart_page_if_requested():
    st.stop()

with st.container(border=True):
    st.markdown('<div class="nav-label">BIST TARAYICI</div>', unsafe_allow_html=True)
    n1, n2, n3 = st.columns(3)
    with n1:
        if st.button("🏠 Ana Sayfa", type="primary" if st.session_state._app_page == "Ana Sayfa" else "secondary", width="stretch", key="nav_home"):
            if st.session_state._app_page != "Ana Sayfa":
                set_page("Ana Sayfa")
    with n2:
        if st.button("🔎 Tarama", type="primary" if st.session_state._app_page == "Tarama" else "secondary", width="stretch", key="nav_scan"):
            if st.session_state._app_page != "Tarama":
                set_page("Tarama")
    with n3:
        total_results = sum(len(st.session_state._result_sets.get(n) or []) for n in ["VWAP", "Üçgen", "Düşen Trend", "Alternasyon"])
        if st.button(f"📊 Sonuçlar · {total_results}", type="primary" if st.session_state._app_page == "Sonuçlar" else "secondary", width="stretch", key="nav_results"):
            if st.session_state._app_page != "Sonuçlar":
                set_page("Sonuçlar", result_focus="Karar Tablosu")
st.markdown('<div class="nav-spacer"></div>', unsafe_allow_html=True)

notice = st.session_state.pop("_job_start_notice", None)
if notice:
    st.success(notice)
render_live_scan_status()

page = st.session_state._app_page
if page == "Ana Sayfa":
    render_home()
elif page == "Tarama":
    render_scan_page()
else:
    render_results_page()

st.caption("Yahoo Finance verisi gecikmeli olabilir. Yükseliş puanı bir yatırım garantisi değil, teknik adayları sıralama aracıdır.")
