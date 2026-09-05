# -*- coding: utf-8 -*-
"""
chart_helpers.py — V5.3 TradingView gesture kontrollü grafik motoru.

Amaç:
- Grafik etkileşimini el yapımı canvas gesture kodundan çıkarıp TradingView'in
  açık kaynak Lightweight Charts motoruna vermek.
- Mobilde grafik gövdesinde X+Y serbest pan, iki parmak pinch zoom,
  sağ fiyat ekseninde dikey scale ve alt zaman ekseninde yatay scale.
- Ayrı hacim paneli YOK.
- Normal fiyat mumlarının gövde genişliği hacim yüzdelik sırasına göre değişir:
  yüksek hacim = daha geniş/şişkin gövde, düşük hacim = daha ince gövde.

Tarama / sinyal mantığı bu dosyada değildir.
"""

from __future__ import annotations

import json
import math
import hashlib
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

try:
    from lightweight_charts_v5 import lightweight_charts_v5_component
except Exception:
    lightweight_charts_v5_component = None

VWAP_COLORS = {1: "#089981", 2: "#2962FF", 3: "#D89B16"}
CURRENCY_AXIS_LABELS = {"TRY": "TL", "USD": "$", "EUR": "€"}

# TradingView'e yakın standart mum renkleri. Hacim renk ile değil gövde eniyle anlatılır.
UP_COLOR = "#089981"
DOWN_COLOR = "#F23645"

LWC_CDN = "https://cdn.jsdelivr.net/npm/lightweight-charts@5.2.1/dist/lightweight-charts.standalone.production.js"


def _finite(v: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _volume_rank(volume: pd.Series) -> List[float]:
    """0..1 hacim yüzdelik sırası; aşırı değerler gövde farkını ezmesin."""
    v = pd.to_numeric(volume, errors="coerce").fillna(0.0)
    if len(v) <= 1:
        return [1.0] * len(v)
    r = v.rank(pct=True, method="average").clip(0.0, 1.0)
    return [float(x) for x in r]


def _date_label(ts: Any, intraday: bool) -> str:
    try:
        p = pd.Timestamp(ts)
        return p.strftime("%d.%m %H:%M" if intraday else "%d.%m.%Y")
    except Exception:
        return str(ts)


def _chart_time(ts: Any, fallback_i: int, intraday: bool) -> int:
    """Lightweight Charts UTCTimestamp.

    Veri çekirdeğinde BIST saatleri çoğunlukla timezone-naive tutuluyor. Naive zamanı
    Europe/Istanbul kabul ederek epoch'a çeviriyoruz; böylece mobil eksende saat 3 saat
    kaymıyor. Tarih okunamazsa düzeni bozmamak için monoton sentetik zaman kullanılır.
    """
    try:
        p = pd.Timestamp(ts)
        if p.tzinfo is None:
            p = p.tz_localize("Europe/Istanbul", ambiguous="NaT", nonexistent="shift_forward")
            if pd.isna(p):
                raise ValueError("ambiguous time")
        else:
            p = p.tz_convert("Europe/Istanbul")
        return int(p.timestamp())
    except Exception:
        step = 3600 if intraday else 86400
        return int(1_700_000_000 + fallback_i * step)


def _candles_from_df(df: pd.DataFrame, period: str = "") -> List[Dict[str, Any]]:
    intraday = str(period) in ("1h", "4h")
    ranks = _volume_rank(df.get("Volume", pd.Series([0] * len(df))))
    out: List[Dict[str, Any]] = []
    prev_time: Optional[int] = None
    for i, row in df.reset_index(drop=True).iterrows():
        o = _finite(row.get("Open")); h = _finite(row.get("High")); l = _finite(row.get("Low")); c = _finite(row.get("Close"))
        if None in (o, h, l, c):
            continue
        t = _chart_time(row.get("Date", i), i, intraday)
        # Lightweight Charts times must be strictly ascending in setData.
        if prev_time is not None and t <= prev_time:
            t = prev_time + (3600 if intraday else 86400)
        prev_time = t
        vol = _finite(row.get("Volume"), 0.0) or 0.0
        rank = ranks[i] if i < len(ranks) else 0.5
        up = c >= o
        out.append({
            "i": int(i),
            "time": int(t),
            "label": _date_label(row.get("Date", i), intraday),
            "open": o, "high": h, "low": l, "close": c,
            "volume": vol,
            "vr": round(float(rank), 6),
            "color": UP_COLOR if up else DOWN_COLOR,
        })
    return out


def _series_points(series: Any) -> List[Dict[str, float]]:
    pts: List[Dict[str, float]] = []
    try:
        vals = series.values if hasattr(series, "values") else list(series)
        for i, val in enumerate(vals):
            y = _finite(val)
            if y is not None:
                pts.append({"i": int(i), "y": y})
    except Exception:
        pass
    return pts


def _base_spec(df: pd.DataFrame, period: str, focus_start: Optional[int] = None,
               focus_end: Optional[int] = None, currency: str = "TRY") -> Dict[str, Any]:
    candles = _candles_from_df(df, period)
    n = len(candles)
    if n == 0:
        return {"candles": [], "lines": [], "markers": [], "rects": [], "focus": [0, 1]}
    if focus_start is None:
        focus_start = max(0, n - 80)
    if focus_end is None:
        focus_end = n - 1
    focus_start = max(0, min(n - 1, int(focus_start)))
    focus_end = max(focus_start, min(n - 1, int(focus_end)))
    if focus_end - focus_start + 1 < 45:
        focus_start = max(0, focus_end - 44)
    if focus_end - focus_start + 1 > 105:
        focus_start = max(0, focus_end - 104)
    return {
        "candles": candles,
        "lines": [],
        "markers": [],
        "rects": [],
        "focus": [focus_start, focus_end + 1.5],
        "currency": CURRENCY_AXIS_LABELS.get(currency, currency),
        "period": str(period or ""),
        "lastPrice": candles[-1]["close"],
        "lastUp": bool(candles[-1]["close"] >= candles[-1]["open"]),
    }


def _add_line(spec: Dict[str, Any], points: List[Dict[str, float]], color: str,
              width: float = 2.0, dashed: bool = False) -> None:
    if len(points) >= 2:
        spec["lines"].append({"points": points, "color": color, "width": width, "dashed": dashed})


def _add_marker(spec: Dict[str, Any], i: int, y: float, color: str, shape: str = "triangle") -> None:
    yy = _finite(y)
    if yy is not None:
        spec["markers"].append({"i": int(i), "y": yy, "color": color, "shape": shape})


def _render_lwc_chart(spec: Dict[str, Any], key: Optional[str] = None, height: int = 650) -> None:
    """V5.4: Streamlit-native Lightweight Charts component.

    CDN/iframe script yükleme yoktur. Grafik JavaScript'i Python paketinin kendi
    Streamlit component build'i içinden gelir; bu nedenle Safari/Streamlit Cloud
    üzerinde dış CDN engeli yüzünden boş grafik kalmaz.
    """
    if lightweight_charts_v5_component is None:
        import streamlit as st
        st.error("Grafik bileşeni kurulamadı. requirements.txt içindeki streamlit-lightweight-charts-v5 paketini kontrol edin.")
        return

    candles = spec.get("candles") or []
    if not candles:
        import streamlit as st
        st.info("Grafik verisi yok.")
        return

    mobile_height = max(int(height), 650)
    intraday = str(spec.get("period") or "") in ("1h", "4h")
    last = _finite(spec.get("lastPrice"), 0.0) or 0.0
    if abs(last) >= 100:
        precision = 2
    elif abs(last) >= 1:
        precision = 3
    else:
        precision = 4

    chart_opts = {
        "layout": {
            "background": {"type": "solid", "color": "#FFFFFF"},
            "textColor": "#4B5563",
            "fontFamily": "-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif",
            "fontSize": 12,
        },
        "grid": {
            "vertLines": {"visible": False},
            "horzLines": {"visible": True, "color": "#EEF1F4"},
        },
        "rightPriceScale": {
            "visible": True,
            "borderVisible": False,
            "scaleMargins": {"top": 0.08, "bottom": 0.08},
            "entireTextOnly": True,
        },
        "leftPriceScale": {"visible": False},
        "timeScale": {
            "visible": True,
            "borderVisible": False,
            "timeVisible": intraday,
            "secondsVisible": False,
            "barSpacing": 6,
            "minBarSpacing": 1.2,
            "rightOffset": 2,
            "fixLeftEdge": False,
            "fixRightEdge": False,
            "lockVisibleTimeRangeOnResize": False,
        },
        "handleScroll": {
            "mouseWheel": True,
            "pressedMouseMove": True,
            "horzTouchDrag": True,
            "vertTouchDrag": True,
        },
        "handleScale": {
            "axisPressedMouseMove": {"time": True, "price": True},
            "axisDoubleClickReset": {"time": True, "price": True},
            "mouseWheel": True,
            "pinch": True,
        },
        "kineticScroll": {"mouse": True, "touch": True},
    }

    candle_data = []
    for c in candles:
        candle_data.append({
            "time": int(c["time"]),
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"]),
            "color": c.get("color") or (UP_COLOR if c["close"] >= c["open"] else DOWN_COLOR),
            "borderColor": c.get("color") or (UP_COLOR if c["close"] >= c["open"] else DOWN_COLOR),
            "wickColor": c.get("color") or (UP_COLOR if c["close"] >= c["open"] else DOWN_COLOR),
        })

    marker_items = []
    for m in (spec.get("markers") or []):
        try:
            i = max(0, min(len(candles) - 1, int(round(float(m.get("i", 0))))))
            marker_items.append({
                "time": int(candles[i]["time"]),
                "position": "aboveBar",
                "color": m.get("color") or "#F59E0B",
                "shape": "arrowUp",
                "text": "",
            })
        except Exception:
            pass

    series = [{
        "type": "Candlestick",
        "data": candle_data,
        "options": {
            "upColor": UP_COLOR,
            "downColor": DOWN_COLOR,
            "borderVisible": False,
            "wickUpColor": UP_COLOR,
            "wickDownColor": DOWN_COLOR,
            "priceScaleId": "right",
            "lastValueVisible": True,
            "priceLineVisible": True,
            "priceLineStyle": 2,
            "priceFormat": {
                "type": "price",
                "precision": precision,
                "minMove": 10 ** (-precision),
            },
        },
        "markers": marker_items,
    }]

    def _time_at(i: Any) -> Optional[int]:
        try:
            ii = max(0, min(len(candles) - 1, int(round(float(i)))))
            return int(candles[ii]["time"])
        except Exception:
            return None

    for ln in (spec.get("lines") or []):
        pts = []
        for pt in (ln.get("points") or []):
            t = _time_at(pt.get("i"))
            y = _finite(pt.get("y"))
            if t is not None and y is not None:
                pts.append({"time": t, "value": float(y)})
        if len(pts) >= 2:
            series.append({
                "type": "Line",
                "data": pts,
                "options": {
                    "color": ln.get("color") or "#2962FF",
                    "lineWidth": max(1, min(4, int(round(float(ln.get("width") or 2))))),
                    "lineStyle": 2 if ln.get("dashed") else 0,
                    "crosshairMarkerVisible": False,
                    "lastValueVisible": False,
                    "priceLineVisible": False,
                    "priceScaleId": "right",
                },
            })

    # Alternasyon bölgesini iki yatay sınır çizgisiyle göster.
    for rc in (spec.get("rects") or []):
        t0, t1 = _time_at(rc.get("x0")), _time_at(rc.get("x1"))
        for y0 in (rc.get("y0"), rc.get("y1")):
            yy = _finite(y0)
            if t0 is None or t1 is None or yy is None:
                continue
            series.append({
                "type": "Line",
                "data": [{"time": t0, "value": float(yy)}, {"time": t1, "value": float(yy)}],
                "options": {
                    "color": rc.get("color") or "#D5A800",
                    "lineWidth": 1,
                    "lineStyle": 2,
                    "crosshairMarkerVisible": False,
                    "lastValueVisible": False,
                    "priceLineVisible": False,
                    "priceScaleId": "right",
                },
            })

    chart_cfg = {
        "chart": chart_opts,
        "series": series,
        "height": mobile_height,
    }

    # Component kendi bundle'ını taşır; dış CDN veya components.html script'i kullanılmaz.
    lightweight_charts_v5_component(
        name=str(key or "bist_chart"),
        charts=[chart_cfg],
        height=mobile_height,
        key=str(key or "bist_chart"),
    )

def render_vwap_chart(sym: str, r: Dict[str, Any], key: Optional[str] = None) -> None:
    df = r["df"].reset_index(drop=True)
    n = len(df)
    cross_idx = int(r.get("cross_idx", max(0, n - 1)))
    spec = _base_spec(df, str(r.get("period", "")), max(0, cross_idx - 55), n - 1, str(r.get("currency", "TRY")))
    for info in r.get("chain", []):
        lvl = int(info.get("level", 0) or 0)
        _add_line(spec, _series_points(info.get("vwap")), VWAP_COLORS.get(lvl, "#7b8492"), 2.0,
                  dashed=(lvl != int(r.get("level", 0) or 0)))
    if 0 <= cross_idx < n:
        _add_marker(spec, cross_idx, float(df["Close"].iloc[cross_idx]), "#D99B16", "star")
    tr = r.get("trendline") or {}
    if tr.get("matched") and tr.get("line"):
        ln = tr["line"]; s=_finite(ln.get("slope")); b=_finite(ln.get("intercept")); x1=int(ln.get("x1",0)); x2=int(ln.get("x2",0)); cx=int(tr.get("cross_idx",x2))
        if s is not None and b is not None:
            _add_line(spec,[{"i":x1,"y":s*x1+b},{"i":x2,"y":s*x2+b}],"#F23645",2.4,False)
            _add_line(spec,[{"i":x2,"y":s*x2+b},{"i":cx,"y":s*cx+b}],"#F23645",1.8,True)
            if 0<=cx<n:_add_marker(spec,cx,float(df["Close"].iloc[cx]),"#F23645","triangle")
    _render_lwc_chart(spec, key=key, height=650)


def render_triangle_chart(sym: str, r: Dict[str, Any], key: Optional[str] = None) -> None:
    df = r["df"].reset_index(drop=True); n=len(df)
    upper,lower=r["upper"],r["lower"]
    start=min(int(upper.get("x1",0)),int(lower.get("x1",0)))
    spec=_base_spec(df,str(r.get("period","")),max(0,start-8),n-1,"TRY")
    apex_x=_finite(r.get("apex_x"),n-1) or n-1; draw_to=min(float(apex_x), n-1+8)
    for ln,col in ((upper,"#F23645"),(lower,"#089981")):
        s=_finite(ln.get("slope"));b=_finite(ln.get("intercept"));x1=int(ln.get("x1",0));x2=int(ln.get("x2",0))
        if s is not None and b is not None:
            _add_line(spec,[{"i":x1,"y":s*x1+b},{"i":x2,"y":s*x2+b}],col,2.4,False)
            _add_line(spec,[{"i":x2,"y":s*x2+b},{"i":draw_to,"y":s*draw_to+b}],col,1.8,True)
    apy=_finite(r.get("apex_y"))
    if apy is not None:_add_marker(spec,int(round(apex_x)),apy,"#D99B16","cross")
    _render_lwc_chart(spec,key=key,height=650)


def render_trendline_chart(sym: str, r: Dict[str, Any], key: Optional[str] = None) -> None:
    df=r["df"].reset_index(drop=True); n=len(df); ln=r["line"]
    x1=int(ln.get("x1",0));x2=int(ln.get("x2",0));cross=int(r.get("cross_idx",x2))
    spec=_base_spec(df,str(r.get("period","")),max(0,x1-8),n-1,"TRY")
    s=_finite(ln.get("slope"));b=_finite(ln.get("intercept"))
    if s is not None and b is not None:
        _add_line(spec,[{"i":x1,"y":s*x1+b},{"i":x2,"y":s*x2+b}],"#F23645",2.5,False)
        _add_line(spec,[{"i":x2,"y":s*x2+b},{"i":cross,"y":s*cross+b}],"#F23645",1.8,True)
    if 0<=cross<n:_add_marker(spec,cross,float(df["Close"].iloc[cross]),"#F23645","triangle")
    _render_lwc_chart(spec,key=key,height=650)


def render_alternation_chart(sym: str, r: Dict[str, Any], key: Optional[str] = None) -> None:
    df=r["df"].reset_index(drop=True); n=len(df);start=int(r.get("start_idx",max(0,n-10)));end=int(r.get("end_idx",n-1))
    spec=_base_spec(df,str(r.get("period","")),max(0,start-20),n-1,"TRY")
    sub=df.iloc[max(0,start):min(n,end+1)]
    if not sub.empty:
        lo=float(sub["Low"].min());hi=float(sub["High"].max());pad=max((hi-lo)*.06,abs(hi)*.004,.01)
        spec["rects"].append({"x0":start-.5,"x1":end+.5,"y0":lo-pad,"y1":hi+pad,"color":"#D5A800","fill":"rgba(245,197,66,.04)","dashed":True})
        pts=[{"i":i,"y":float(df["Close"].iloc[i])} for i in range(max(0,start),min(n,end+1))]
        _add_line(spec,pts,"#D5A800",1.7,True)
    _render_lwc_chart(spec,key=key,height=650)


def _same_df_shape(a: Any, b: Any) -> bool:
    try:
        if not isinstance(a, pd.DataFrame) or not isinstance(b, pd.DataFrame):
            return False
        if len(a) != len(b):
            return False
        if "Date" in a.columns and "Date" in b.columns:
            da = pd.to_datetime(a["Date"], errors="coerce").reset_index(drop=True)
            db = pd.to_datetime(b["Date"], errors="coerce").reset_index(drop=True)
            return bool(da.equals(db))
        return True
    except Exception:
        return False


def _overlay_signals_on_spec(spec: Dict[str, Any], df: pd.DataFrame, signals: Dict[str, Any]) -> None:
    n = len(df)
    vwap_r = signals.get("VWAP")
    if isinstance(vwap_r, dict) and _same_df_shape(vwap_r.get("df"), df):
        active_lvl = int(vwap_r.get("level", 0) or 0)
        for info in vwap_r.get("chain", []):
            lvl = int(info.get("level", 0) or 0)
            _add_line(spec, _series_points(info.get("vwap")), VWAP_COLORS.get(lvl, "#7b8492"), 2.0, dashed=(lvl != active_lvl))
        cross_idx = int(vwap_r.get("cross_idx", max(0, n - 1)))
        if 0 <= cross_idx < n:
            _add_marker(spec, cross_idx, float(df["Close"].iloc[cross_idx]), "#D99B16", "star")

    tri_r = signals.get("Üçgen")
    if isinstance(tri_r, dict) and _same_df_shape(tri_r.get("df"), df):
        upper, lower = tri_r.get("upper") or {}, tri_r.get("lower") or {}
        apex_x = _finite(tri_r.get("apex_x"), n - 1) or n - 1
        draw_to = min(float(apex_x), n - 1 + 8)
        for ln, col in ((upper, "#F23645"), (lower, "#089981")):
            s = _finite(ln.get("slope")); b = _finite(ln.get("intercept")); x1 = int(ln.get("x1", 0)); x2 = int(ln.get("x2", 0))
            if s is not None and b is not None:
                _add_line(spec, [{"i": x1, "y": s * x1 + b}, {"i": x2, "y": s * x2 + b}], col, 2.4, False)
                _add_line(spec, [{"i": x2, "y": s * x2 + b}, {"i": draw_to, "y": s * draw_to + b}], col, 1.8, True)
        apy = _finite(tri_r.get("apex_y"))
        if apy is not None:
            _add_marker(spec, int(round(apex_x)), apy, "#D99B16", "cross")

    tl_r = signals.get("Düşen Trend")
    if isinstance(tl_r, dict) and _same_df_shape(tl_r.get("df"), df):
        ln = tl_r.get("line") or {}
        x1 = int(ln.get("x1", 0)); x2 = int(ln.get("x2", 0)); cross = int(tl_r.get("cross_idx", x2))
        s = _finite(ln.get("slope")); b = _finite(ln.get("intercept"))
        if s is not None and b is not None:
            _add_line(spec, [{"i": x1, "y": s * x1 + b}, {"i": x2, "y": s * x2 + b}], "#F23645", 2.5, False)
            _add_line(spec, [{"i": x2, "y": s * x2 + b}, {"i": cross, "y": s * cross + b}], "#F23645", 1.8, True)
        if 0 <= cross < n:
            _add_marker(spec, cross, float(df["Close"].iloc[cross]), "#F23645", "triangle")

    alt_r = signals.get("Alternasyon")
    if isinstance(alt_r, dict) and _same_df_shape(alt_r.get("df"), df):
        start = int(alt_r.get("start_idx", max(0, n - 10))); end = int(alt_r.get("end_idx", n - 1))
        sub = df.iloc[max(0, start):min(n, end + 1)]
        if not sub.empty:
            lo = float(sub["Low"].min()); hi = float(sub["High"].max()); pad = max((hi - lo) * .06, abs(hi) * .004, .01)
            spec["rects"].append({"x0": start - .5, "x1": end + .5, "y0": lo - pad, "y1": hi + pad, "color": "#D5A800", "fill": "rgba(245,197,66,.04)", "dashed": True})
            pts = [{"i": i, "y": float(df["Close"].iloc[i])} for i in range(max(0, start), min(n, end + 1))]
            _add_line(spec, pts, "#D5A800", 1.7, True)


def render_combined_chart(sym: str, payload: Dict[str, Any], key: Optional[str] = None) -> None:
    """Aynı hissedeki tüm bulunan sinyalleri grafik sayfasında gösterir.

    Farklı tarama periyotları aynı mum eksenine zorla bindirilmez; bu teknik olarak
    hatalı olurdu. Aynı periyottaki sinyaller tek panelde üst üste çizilir, farklı
    periyotlar ise aynı sayfada ayrı panellerde gösterilir. Masaüstünde iki sütun,
    mobilde Streamlit/CSS sayesinde tek sütun görünür.
    """
    signals = (payload or {}).get("signals") or {}
    valid = {}
    for name, item in signals.items():
        if isinstance(item, dict) and isinstance(item.get("df"), pd.DataFrame) and len(item.get("df")) > 0:
            valid[name] = item
    if not valid:
        st.warning("Birleşik grafiği çizmek için veri bulunamadı.")
        return

    groups: Dict[str, Dict[str, Any]] = {}
    for name, item in valid.items():
        period = str(item.get("period") or "unknown")
        df = item.get("df").reset_index(drop=True)
        group_key = period
        if group_key in groups and not _same_df_shape(groups[group_key]["df"], df):
            group_key = f"{period}:{name}"
        groups.setdefault(group_key, {"period": period, "df": df, "signals": {}})
        groups[group_key]["signals"][name] = item

    ordered = list(groups.values())
    cols = st.columns(2) if len(ordered) > 1 else [st.container()]
    for idx, group in enumerate(ordered):
        holder = cols[idx % 2] if len(ordered) > 1 else cols[0]
        with holder:
            names = list(group["signals"].keys())
            label = " + ".join(names)
            st.markdown(f"**{group['period']} · {label}**")
            df = group["df"]
            n = len(df)
            focus_start = max(0, n - 80)
            spec = _base_spec(df, group["period"], focus_start, n - 1, str(next(iter(group["signals"].values())).get("currency", "TRY")))
            _overlay_signals_on_spec(spec, df, group["signals"])
            _render_lwc_chart(spec, key=f"{key or 'combo'}_{idx}", height=470 if len(ordered) > 1 else 650)
