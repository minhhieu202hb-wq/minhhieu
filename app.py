import streamlit as st
import pandas as pd
import requests
import json
import os
import datetime

st.set_page_config(
    page_title="Bot Trading Mobile",
    page_icon="📱",
    layout="centered",
    initial_sidebar_state="collapsed"
)

DATA_FILE = "trading_data.json"
VN_TZ = datetime.timezone(datetime.timedelta(hours=7))

# --- CSS TỐI ƯU GIAO DIỆN CHO ĐIỆN THOẠI ---
st.markdown("""
<style>
    /* Thu gọn lề trên dưới để tận dụng diện tích màn hình điện thoại */
    .block-container {
        padding-top: 1.1rem !important;
        padding-bottom: 2.5rem !important;
        padding-left: 0.85rem !important;
        padding-right: 0.85rem !important;
        max-width: 680px !important;
    }
    /* Nút bấm lớn dễ thao tác bằng ngón tay */
    div.stButton > button {
        min-height: 48px !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        font-size: 15px !important;
    }
    /* Lưới thẻ số liệu 2x2 sắc nét, không bị cắt chữ trên màn hình hẹp */
    .m-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin-bottom: 12px;
    }
    .m-card {
        background-color: rgba(128, 128, 128, 0.10);
        border: 1px solid rgba(128, 128, 128, 0.22);
        border-radius: 12px;
        padding: 10px 12px;
    }
    .m-label {
        font-size: 12px;
        opacity: 0.78;
        margin-bottom: 2px;
    }
    .m-val {
        font-size: 18px;
        font-weight: 700;
        line-height: 1.25;
    }
    .m-sub {
        font-size: 11.5px;
        margin-top: 3px;
        opacity: 0.85;
    }
    .pos-green { color: #16a34a; font-weight: 600; }
    .pos-red { color: #dc2626; font-weight: 600; }
    /* Thẻ lệnh đang chạy & gợi ý Entry */
    .trade-card {
        background-color: rgba(128, 128, 128, 0.08);
        border-left: 4px solid #2563eb;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 10px;
        font-size: 14px;
        line-height: 1.55;
    }
    .trade-buy { border-left-color: #16a34a; }
    .trade-sell { border-left-color: #dc2626; }
    /* Tối ưu thanh Tab trên điện thoại */
    button[data-baseweb="tab"] {
        font-size: 14px !important;
        font-weight: 600 !important;
        padding: 8px 10px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- CẤU HÌNH CHỈ BÁO RIÊNG CHO TỪNG CẶP TIỀN ---
PAIR_CONFIG = {
    "XAU/USD": {
        "contract_size": 100, "decimals": 2, "usd_base": False,
        "ema_fast": 21, "ema_slow": 89, "sma_trend": 200,
        "rsi_buy": 55, "rsi_sell": 45,
        "macd_fast": 12, "macd_slow": 26, "macd_sig": 9,
        "adx_min": 20, "sl_mult": 1.8, "tp_mult": 3.2,
        "desc": "Fibonacci EMA 21/89 + ADX >= 20 (Chống quét râu Vàng)"
    },
    "EUR/USD": {
        "contract_size": 100000, "decimals": 5, "usd_base": False,
        "ema_fast": 20, "ema_slow": 50, "sma_trend": 200,
        "rsi_buy": 52, "rsi_sell": 48,
        "macd_fast": 12, "macd_slow": 26, "macd_sig": 9,
        "adx_min": 20, "sl_mult": 1.8, "tp_mult": 2.7,
        "desc": "Chuẩn tổ chức EMA 20/50 + RSI 52/48 (R:R 1:1.5)"
    },
    "GBP/USD": {
        "contract_size": 100000, "decimals": 5, "usd_base": False,
        "ema_fast": 21, "ema_slow": 55, "sma_trend": 200,
        "rsi_buy": 53, "rsi_sell": 47,
        "macd_fast": 12, "macd_slow": 26, "macd_sig": 9,
        "adx_min": 22, "sl_mult": 2.2, "tp_mult": 3.3,
        "desc": "EMA 21/55 + SL rộng 2.2 ATR (Chống giật râu GBP)"
    },
    "AUD/USD": {
        "contract_size": 100000, "decimals": 5, "usd_base": False,
        "ema_fast": 20, "ema_slow": 50, "sma_trend": 200,
        "rsi_buy": 52, "rsi_sell": 48,
        "macd_fast": 8, "macd_slow": 21, "macd_sig": 5,
        "adx_min": 18, "sl_mult": 1.8, "tp_mult": 2.7,
        "desc": "Tiền hàng hóa: EMA 20/50 + MACD nhanh (8,21,5)"
    },
    "USD/JPY": {
        "contract_size": 100000, "decimals": 3, "usd_base": True,
        "ema_fast": 21, "ema_slow": 55, "sma_trend": 200,
        "rsi_buy": 55, "rsi_sell": 45,
        "macd_fast": 12, "macd_slow": 26, "macd_sig": 9,
        "adx_min": 22, "sl_mult": 1.8, "tp_mult": 3.2,
        "desc": "Bám trend dài cặp Yên: EMA 21/55 + ADX >= 22"
    },
    "USD/CHF": {
        "contract_size": 100000, "decimals": 5, "usd_base": True,
        "ema_fast": 20, "ema_slow": 50, "sma_trend": 200,
        "rsi_buy": 52, "rsi_sell": 48,
        "macd_fast": 12, "macd_slow": 26, "macd_sig": 9,
        "adx_min": 20, "sl_mult": 1.8, "tp_mult": 2.7,
        "desc": "Chuẩn Âu: EMA 20/50 + RSI 52/48 (R:R 1:1.5)"
    },
    "USD/CAD": {
        "contract_size": 100000, "decimals": 5, "usd_base": True,
        "ema_fast": 20, "ema_slow": 50, "sma_trend": 200,
        "rsi_buy": 52, "rsi_sell": 48,
        "macd_fast": 8, "macd_slow": 21, "macd_sig": 5,
        "adx_min": 19, "sl_mult": 1.8, "tp_mult": 2.7,
        "desc": "Tiền dầu mỏ: EMA 20/50 + MACD nhanh (8,21,5)"
    },
}

def gio_vn_hien_tai():
    return datetime.datetime.now(VN_TZ).strftime("%d/%m %H:%M:%S (VN)")

# --- 1. LƯU & ĐỌC DỮ LIỆU TỪ FILE JSON (KHÔNG BỊ RESET KHI F5 HOẶC THOÁT WEB) ---
def load_data():
    default_data = {
        "balance": 1000.0,
        "initial_balance": 1000.0,
        "lot_size": 0.01,
        "selected_symbol": "XAU/USD",
        "auto_refresh": True,
        "refresh_sec": 120,
        "open_trades": {},
        "trade_history": []
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in default_data.items():
                    if k not in data:
                        data[k] = v
                if data["selected_symbol"] not in PAIR_CONFIG:
                    data["selected_symbol"] = "XAU/USD"
                return data
        except Exception:
            return default_data
    return default_data

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def tinh_pnl(symbol, trade_type, entry, exit_price, lot):
    cfg = PAIR_CONFIG[symbol]
    diff = (exit_price - entry) if trade_type == "BUY" else (entry - exit_price)
    raw_pnl = diff * cfg["contract_size"] * lot
    if cfg["usd_base"] and exit_price > 0:
        return raw_pnl / exit_price
    return raw_pnl

# --- 2. LẤY DỮ LIỆU (MÚI GIỜ VIỆT NAM) & PHÂN TÍCH KỸ THUẬT ---
def lay_du_lieu_h1(symbol, show_error=True):
    api_key = "05c4ba66953c4eb79030baf0da24f012"
    url = (
        f"https://api.twelvedata.com/time_series?"
        f"symbol={symbol}&interval=1h&outputsize=300"
        f"&timezone=Asia/Ho_Chi_Minh&apikey={api_key}"
    )
    try:
        res = requests.get(url, timeout=15).json()
        if "values" in res:
            df = pd.DataFrame(res["values"]).iloc[::-1].reset_index(drop=True)
            for col in ["open", "high", "low", "close"]:
                df[col] = df[col].astype(float)
            df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "datetime": "Date"}, inplace=True)
            return df
        else:
            if show_error:
                st.error(f"Lỗi API ({symbol}): {res.get('message', 'Vượt giới hạn gọi API')}")
            return None
    except Exception as e:
        if show_error:
            st.error(f"Lỗi kết nối mạng ({symbol}): {e}")
        return None

def phan_tich_ky_thuat(df, symbol):
    cfg = PAIR_CONFIG[symbol]

    df["EMA_Fast"] = df["Close"].ewm(span=cfg["ema_fast"], adjust=False).mean()
    df["EMA_Slow"] = df["Close"].ewm(span=cfg["ema_slow"], adjust=False).mean()
    df["SMA_Trend"] = df["Close"].rolling(window=cfg["sma_trend"]).mean()

    df["BB_Mid"] = df["Close"].rolling(window=20).mean()
    df["BB_Std"] = df["Close"].rolling(window=20).std()
    df["BB_Up"] = df["BB_Mid"] + (df["BB_Std"] * 2)
    df["BB_Low"] = df["BB_Mid"] - (df["BB_Std"] * 2)

    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0.0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1/14, adjust=False).mean().replace(0, 1e-10)
    df["RSI_14"] = 100 - (100 / (1 + (gain / loss)))

    df["MACD"] = (
        df["Close"].ewm(span=cfg["macd_fast"], adjust=False).mean()
        - df["Close"].ewm(span=cfg["macd_slow"], adjust=False).mean()
    )
    df["MACD_Signal"] = df["MACD"].ewm(span=cfg["macd_sig"], adjust=False).mean()

    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR_14"] = true_range.ewm(alpha=1/14, adjust=False).mean()

    up_move = df["High"].diff()
    down_move = -df["Low"].diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    atr_safe = df["ATR_14"].replace(0, 1e-10)
    plus_di = 100 * (plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_safe)
    minus_di = 100 * (minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_safe)
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-10))
    df["ADX_14"] = dx.ewm(alpha=1/14, adjust=False).mean()

    df["Bullish_Score"] = 0
    df.loc[df["Close"] > df["EMA_Fast"], "Bullish_Score"] += 1
    df.loc[df["Close"] <= df["EMA_Fast"], "Bullish_Score"] -= 1
    df.loc[df["EMA_Fast"] > df["EMA_Slow"], "Bullish_Score"] += 1
    df.loc[df["EMA_Fast"] <= df["EMA_Slow"], "Bullish_Score"] -= 1
    df.loc[df["Close"] > df["SMA_Trend"], "Bullish_Score"] += 1
    df.loc[df["Close"] <= df["SMA_Trend"], "Bullish_Score"] -= 1
    df.loc[df["RSI_14"] > cfg["rsi_buy"], "Bullish_Score"] += 1
    df.loc[df["RSI_14"] < cfg["rsi_sell"], "Bullish_Score"] -= 1
    df.loc[df["MACD"] > df["MACD_Signal"], "Bullish_Score"] += 1
    df.loc[df["MACD"] <= df["MACD_Signal"], "Bullish_Score"] -= 1

    return df.dropna().reset_index(drop=True)

def danh_gia_tin_hieu(df_ptkt, symbol):
    cfg = PAIR_CONFIG[symbol]
    nen_ht = df_ptkt.iloc[-1]
    gia_ht = nen_ht["Close"]
    gia_mo = nen_ht["Open"]
    ema_fast = nen_ht["EMA_Fast"]
    ema_slow = nen_ht["EMA_Slow"]
    bb_up = nen_ht["BB_Up"]
    bb_low = nen_ht["BB_Low"]
    atr = nen_ht["ATR_14"]
    adx = nen_ht["ADX_14"]
    diem = int(nen_ht["Bullish_Score"])

    sl_khoang = atr * cfg["sl_mult"]
    tp_khoang = atr * cfg["tp_mult"]

    kich_ban = "BUY (LONG)" if diem >= 3 else ("SELL (SHORT)" if diem <= -3 else "ĐỨNG NGOÀI")
    dk1 = dk2 = dk3 = False

    if kich_ban == "BUY (LONG)":
        dk1 = diem >= 4
        dk2 = adx >= cfg["adx_min"]
        dk3 = (gia_ht < bb_up) and (abs(gia_ht - ema_fast) <= atr * 1.0) and (gia_ht > gia_mo)
    elif kich_ban == "SELL (SHORT)":
        dk1 = diem <= -4
        dk2 = adx >= cfg["adx_min"]
        dk3 = (gia_ht > bb_low) and (abs(ema_fast - gia_ht) <= atr * 1.0) and (gia_ht < gia_mo)

    dieu_kien_vao_lenh = dk1 and dk2 and dk3
    so_dk_dat = int(dk1) + int(dk2) + int(dk3)

    return {
        "nen_ht": nen_ht,
        "gia_ht": gia_ht,
        "gia_mo": gia_mo,
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "sma_trend": nen_ht["SMA_Trend"],
        "rsi": nen_ht["RSI_14"],
        "adx": adx,
        "macd_line": nen_ht["MACD"],
        "macd_signal": nen_ht["MACD_Signal"],
        "bb_up": bb_up,
        "bb_low": bb_low,
        "atr": atr,
        "diem": diem,
        "sl_khoang": sl_khoang,
        "tp_khoang": tp_khoang,
        "kich_ban": kich_ban,
        "dk1": dk1,
        "dk2": dk2,
        "dk3": dk3,
        "so_dk_dat": so_dk_dat,
        "dieu_kien_vao_lenh": dieu_kien_vao_lenh,
    }

def xu_ly_lenh_ao(data, symbol, kq):
    thong_bao = []
    dec = PAIR_CONFIG[symbol]["decimals"]
    nen_ht = kq["nen_ht"]
    gia_ht = kq["gia_ht"]

    if symbol in data["open_trades"]:
        trade = data["open_trades"][symbol]
        trade["Last_Price"] = gia_ht
        dong_lenh = False
        li_do = ""
        gia_khop = 0.0

        if trade["Type"] == "BUY":
            if nen_ht["Low"] <= trade["SL"]:
                dong_lenh, li_do, gia_khop = True, "Chạm SL ❌", trade["SL"]
            elif nen_ht["High"] >= trade["TP"]:
                dong_lenh, li_do, gia_khop = True, "Chạm TP ✅", trade["TP"]
        elif trade["Type"] == "SELL":
            if nen_ht["High"] >= trade["SL"]:
                dong_lenh, li_do, gia_khop = True, "Chạm SL ❌", trade["SL"]
            elif nen_ht["Low"] <= trade["TP"]:
                dong_lenh, li_do, gia_khop = True, "Chạm TP ✅", trade["TP"]

        if dong_lenh:
            pnl = tinh_pnl(symbol, trade["Type"], trade["Entry"], gia_khop, trade["Lot"])
            data["balance"] += pnl
            data["trade_history"].append({
                "Cặp tiền": symbol,
                "Vào lúc (VN)": trade["Time"],
                "Đóng lúc (VN)": nen_ht["Date"],
                "Loại": trade["Type"],
                "Lot": trade["Lot"],
                "Giá Vào": round(trade["Entry"], dec),
                "Giá Khớp": round(gia_khop, dec),
                "Lý do": li_do,
                "Lãi/Lỗ ($)": round(pnl, 2),
                "Số Dư ($)": round(data["balance"], 2)
            })
            del data["open_trades"][symbol]
            save_data(data)
            thong_bao.append(("success", f"🔔 CHỐT {symbol} ({trade['Type']}) — {li_do} | PnL: {pnl:+.2f}$"))
        else:
            save_data(data)

    if symbol not in data["open_trades"] and kq["dieu_kien_vao_lenh"]:
        if kq["kich_ban"] == "BUY (LONG)":
            data["open_trades"][symbol] = {
                "Symbol": symbol,
                "Time": nen_ht["Date"],
                "Type": "BUY",
                "Lot": data["lot_size"],
                "Entry": gia_ht,
                "SL": gia_ht - kq["sl_khoang"],
                "TP": gia_ht + kq["tp_khoang"],
                "Last_Price": gia_ht
            }
            save_data(data)
            thong_bao.append(("info", f"🔔 VÀO LỆNH BUY {symbol} @ {gia_ht:.{dec}f}"))
        elif kq["kich_ban"] == "SELL (SHORT)":
            data["open_trades"][symbol] = {
                "Symbol": symbol,
                "Time": nen_ht["Date"],
                "Type": "SELL",
                "Lot": data["lot_size"],
                "Entry": gia_ht,
                "SL": gia_ht + kq["sl_khoang"],
                "TP": gia_ht - kq["tp_khoang"],
                "Last_Price": gia_ht
            }
            save_data(data)
            thong_bao.append(("info", f"🔔 VÀO LỆNH SELL {symbol} @ {gia_ht:.{dec}f}"))

    return thong_bao

# --- 3. QUÉT TẤT CẢ 7 CẶP TIỀN ---
def quet_tat_ca_cap_tien():
    data = load_data()
    ket_qua_tong_hop = []
    entry_dep_list = []
    tat_ca_thong_bao = []
    symbols = list(PAIR_CONFIG.keys())

    progress = st.progress(0, text="Đang quét 7 cặp tiền...")
    for idx, sym in enumerate(symbols):
        progress.progress((idx + 1) / len(symbols), text=f"Đang quét {sym} ({idx + 1}/{len(symbols)})...")
        df_raw = lay_du_lieu_h1(sym, show_error=False)
        if df_raw is None:
            ket_qua_tong_hop.append({
                "Cặp": sym, "Giá": "Lỗi API", "Điểm": "-",
                "Trạng thái": "⚠️ Quá giới hạn API", "SL": "-", "TP": "-", "Ưu tiên": 3
            })
            continue

        df_ptkt = phan_tich_ky_thuat(df_raw, sym)
        if len(df_ptkt) == 0:
            continue

        kq = danh_gia_tin_hieu(df_ptkt, sym)
        tb = xu_ly_lenh_ao(data, sym, kq)
        tat_ca_thong_bao.extend(tb)

        dec = PAIR_CONFIG[sym]["decimals"]
        gia = kq["gia_ht"]

        if kq["kich_ban"] == "BUY (LONG)":
            sl_val = f"{gia - kq['sl_khoang']:.{dec}f}"
            tp_val = f"{gia + kq['tp_khoang']:.{dec}f}"
        elif kq["kich_ban"] == "SELL (SHORT)":
            sl_val = f"{gia + kq['sl_khoang']:.{dec}f}"
            tp_val = f"{gia - kq['tp_khoang']:.{dec}f}"
        else:
            sl_val, tp_val = "-", "-"

        if kq["dieu_kien_vao_lenh"]:
            danh_gia = f"🌟 {kq['kich_ban']} (3/3)"
            uu_tien = 0
            entry_dep_list.append({
                "symbol": sym,
                "kich_ban": kq["kich_ban"],
                "entry": f"{gia:.{dec}f}",
                "sl": sl_val,
                "tp": tp_val,
                "diem": kq["diem"],
                "adx": round(kq["adx"], 1)
            })
        elif kq["kich_ban"] != "ĐỨNG NGOÀI" and kq["so_dk_dat"] == 2:
            danh_gia = f"⏳ {kq['kich_ban']} (2/3)"
            uu_tien = 1
        elif kq["kich_ban"] != "ĐỨNG NGOÀI":
            danh_gia = f"🔎 {kq['kich_ban']} ({kq['so_dk_dat']}/3)"
            uu_tien = 2
        else:
            danh_gia = "⚪ Đi ngang"
            uu_tien = 3

        ket_qua_tong_hop.append({
            "Cặp": sym,
            "Giá": f"{gia:.{dec}f}",
            "Điểm": f"{kq['diem']:+d}/5",
            "Trạng thái": danh_gia,
            "SL": sl_val,
            "TP": tp_val,
            "Ưu tiên": uu_tien
        })

    progress.empty()
    ket_qua_tong_hop.sort(key=lambda x: x["Ưu tiên"])
    for row in ket_qua_tong_hop:
        del row["Ưu tiên"]

    st.session_state["scan_all_time"] = gio_vn_hien_tai()
    st.session_state["scan_all_table"] = ket_qua_tong_hop
    st.session_state["scan_all_best"] = entry_dep_list
    st.session_state["scan_all_alerts"] = tat_ca_thong_bao

# --- 4. HIỂN THỊ THỐNG KÊ TÀI KHOẢN & WINRATE (GIAO DIỆN MOBILE) ---
def hien_thi_thong_ke(data):
    tong_live_pnl = 0.0
    for sym, t in data["open_trades"].items():
        if sym not in PAIR_CONFIG:
            continue
        gia_tham_chieu = t.get("Last_Price", t["Entry"])
        tong_live_pnl += tinh_pnl(sym, t["Type"], t["Entry"], gia_tham_chieu, t["Lot"])

    equity = data["balance"] + tong_live_pnl
    lich_su = data["trade_history"]
    tong_lenh = len(lich_su)
    lenh_thang = sum(1 for l in lich_su if "TP" in l["Lý do"])
    lenh_thua = tong_lenh - lenh_thang
    winrate = (lenh_thang / tong_lenh * 100) if tong_lenh > 0 else 0.0
    pnl_class = "pos-green" if tong_live_pnl >= 0 else "pos-red"

    st.markdown(f"""
    <div class="m-grid">
        <div class="m-card">
            <div class="m-label">💰 Số dư (Balance)</div>
            <div class="m-val">${data['balance']:,.2f}</div>
            <div class="m-sub">Vốn gốc: ${data['initial_balance']:,.2f}</div>
        </div>
        <div class="m-card">
            <div class="m-label">📈 Vốn thực (Equity)</div>
            <div class="m-val">${equity:,.2f}</div>
            <div class="m-sub">Live: <span class="{pnl_class}">{tong_live_pnl:+.2f} $</span></div>
        </div>
        <div class="m-card">
            <div class="m-label">🏆 Tỉ lệ Winrate</div>
            <div class="m-val">{winrate:.1f}%</div>
            <div class="m-sub">{lenh_thang} Thắng / {lenh_thua} Thua</div>
        </div>
        <div class="m-card">
            <div class="m-label">🧾 Tổng lệnh đã chốt</div>
            <div class="m-val">{tong_lenh}</div>
            <div class="m-sub">Đang mở: {len(data['open_trades'])} lệnh</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.subheader(f"🎯 Lệnh Đang Chạy ({len(data['open_trades'])})")
    if len(data["open_trades"]) > 0:
        for sym, t in data["open_trades"].items():
            if sym not in PAIR_CONFIG:
                continue
            d = PAIR_CONFIG[sym]["decimals"]
            gia_ht_sym = t.get("Last_Price", t["Entry"])
            pnl_sym = tinh_pnl(sym, t["Type"], t["Entry"], gia_ht_sym, t["Lot"])
            icon = "🟢" if t["Type"] == "BUY" else "🔴"
            card_cls = "trade-buy" if t["Type"] == "BUY" else "trade-sell"
            p_cls = "pos-green" if pnl_sym >= 0 else "pos-red"
            st.markdown(f"""
            <div class="trade-card {card_cls}">
                <div><b>{icon} {sym} — {t['Type']} ({t['Lot']} Lot)</b></div>
                <div>🕒 Mở (VN): <code>{t['Time']}</code></div>
                <div>📍 Entry: <code>{t['Entry']:.{d}f}</code> | Giá: <code>{gia_ht_sym:.{d}f}</code></div>
                <div>🎯 TP: <code>{t['TP']:.{d}f}</code> | 🛑 SL: <code>{t['SL']:.{d}f}</code></div>
                <div>💵 PnL tạm tính: <span class="{p_cls}">{pnl_sym:+.2f} USD</span></div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("⚪ Hiện chưa có lệnh nào đang mở.")

    st.subheader("📝 Lịch Sử Đã Chốt")
    if tong_lenh > 0:
        df_hist = pd.DataFrame(lich_su).iloc[::-1]
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
    else:
        st.caption("Chưa có lệnh nào hoàn tất để thống kê.")

# --- 5. PHÂN TÍCH CHI TIẾT CẶP ĐANG CHỌN ---
def hien_thi_phan_tich_chi_tiet(symbol):
    data = load_data()
    cfg = PAIR_CONFIG[symbol]
    dec = cfg["decimals"]
    gio_quet = gio_vn_hien_tai()

    with st.spinner(f"Đang tải dữ liệu {symbol}..."):
        df_raw = lay_du_lieu_h1(symbol)

    if df_raw is not None:
        df_ptkt = phan_tich_ky_thuat(df_raw, symbol)
        if len(df_ptkt) == 0:
            st.error("Chưa đủ 200 nến để tính SMA 200.")
            return

        kq = danh_gia_tin_hieu(df_ptkt, symbol)
        nen_ht = kq["nen_ht"]
        gia_ht = kq["gia_ht"]
        ema_fast = kq["ema_fast"]
        ema_slow = kq["ema_slow"]
        sma_trend = kq["sma_trend"]
        rsi = kq["rsi"]
        adx = kq["adx"]
        macd_line = kq["macd_line"]
        macd_signal = kq["macd_signal"]
        bb_up = kq["bb_up"]
        bb_low = kq["bb_low"]
        atr = kq["atr"]
        diem = kq["diem"]

        # Xử lý vào/chốt lệnh trước để cập nhật trạng thái ngay lập tức
        thong_bao = xu_ly_lenh_ao(data, symbol, kq)
        for loai, msg in thong_bao:
            if loai == "success":
                st.success(msg)
            else:
                st.info(msg)

        st.caption(f"🕒 Quét: **{gio_quet}** | Nến H1: `{nen_ht['Date']}`")

        # Lưới thẻ 2x2 tối ưu cho điện thoại
        st.markdown(f"""
        <div class="m-grid">
            <div class="m-card">
                <div class="m-label">💵 Giá {symbol}</div>
                <div class="m-val">{gia_ht:.{dec}f}</div>
                <div class="m-sub">Điểm Trend: <b>{diem:+d} / 5</b></div>
            </div>
            <div class="m-card">
                <div class="m-label">📊 EMA {cfg['ema_fast']} / EMA {cfg['ema_slow']}</div>
                <div class="m-val">{ema_fast:.{dec}f}</div>
                <div class="m-sub">EMA{cfg['ema_slow']}: {ema_slow:.{dec}f}</div>
            </div>
            <div class="m-card">
                <div class="m-label">🧱 SMA {cfg['sma_trend']} (Trend dài)</div>
                <div class="m-val">{sma_trend:.{dec}f}</div>
                <div class="m-sub">ATR(14): {atr:.{dec}f}</div>
            </div>
            <div class="m-card">
                <div class="m-label">⚡ RSI (14) / ADX (14)</div>
                <div class="m-val">{rsi:.1f} | {adx:.1f}</div>
                <div class="m-sub">ADX chuẩn: &ge; {cfg['adx_min']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Chiến lược khuyến nghị đặt ngay trên đầu cho dễ nhìn trên điện thoại
        if diem >= 3:
            st.success(
                f"🟢 **KHUYẾN NGHỊ: BUY (LONG)** — Xu hướng TĂNG\n\n"
                f"* **Entry:** `{gia_ht:.{dec}f}` (quanh EMA {cfg['ema_fast']}: `{ema_fast:.{dec}f}`)\n"
                f"* **Take Profit ({cfg['tp_mult']} ATR):** `{gia_ht + kq['tp_khoang']:.{dec}f}`\n"
                f"* **Stop Loss ({cfg['sl_mult']} ATR):** `{gia_ht - kq['sl_khoang']:.{dec}f}`"
            )
        elif diem <= -3:
            st.error(
                f"🔴 **KHUYẾN NGHỊ: SELL (SHORT)** — Xu hướng GIẢM\n\n"
                f"* **Entry:** `{gia_ht:.{dec}f}` (quanh EMA {cfg['ema_fast']}: `{ema_fast:.{dec}f}`)\n"
                f"* **Take Profit ({cfg['tp_mult']} ATR):** `{gia_ht - kq['tp_khoang']:.{dec}f}`\n"
                f"* **Stop Loss ({cfg['sl_mult']} ATR):** `{gia_ht + kq['sl_khoang']:.{dec}f}`"
            )
        else:
            st.warning("⚪ **KHUYẾN NGHỊ: ĐỨNG NGOÀI** — Thị trường đi ngang hoặc chỉ báo mâu thuẫn.")

        # Checklist Kịch bản lí tưởng
        st.subheader("📋 Checklist Kịch Bản Lí Tưởng")
        def ve_tich(dk):
            return "✅" if dk else "⬜"

        if kq["kich_ban"] == "BUY (LONG)":
            st.markdown(f"""
- {ve_tich(kq['dk1'])} **Đồng thuận mạnh:** Đạt ít nhất 4/5 điểm TĂNG (`{diem:+d}/5`).
- {ve_tich(kq['dk2'])} **Lực xu hướng (ADX):** ADX = `{adx:.1f}` (cần &ge; `{cfg['adx_min']}`).
- {ve_tich(kq['dk3'])} **Điểm vào chuẩn:** Dưới BB trên (`{bb_up:.{dec}f}`), gần EMA {cfg['ema_fast']} & **nến xanh bật tăng**.
            """)
            if kq["dieu_kien_vao_lenh"]:
                st.success("🎉 Đạt đủ 100% điều kiện kịch bản lí tưởng!")
            else:
                st.info("⏳ Chưa đủ 100% điều kiện, đang đợi nến xác nhận.")
        elif kq["kich_ban"] == "SELL (SHORT)":
            st.markdown(f"""
- {ve_tich(kq['dk1'])} **Đồng thuận mạnh:** Đạt ít nhất 4/5 điểm GIẢM (`{diem:+d}/5`).
- {ve_tich(kq['dk2'])} **Lực xu hướng (ADX):** ADX = `{adx:.1f}` (cần &ge; `{cfg['adx_min']}`).
- {ve_tich(kq['dk3'])} **Điểm vào chuẩn:** Trên BB dưới (`{bb_low:.{dec}f}`), gần EMA {cfg['ema_fast']} & **nến đỏ bật giảm**.
            """)
            if kq["dieu_kien_vao_lenh"]:
                st.success("🎉 Đạt đủ 100% điều kiện kịch bản lí tưởng!")
            else:
                st.info("⏳ Chưa đủ 100% điều kiện, đang đợi nến xác nhận.")
        else:
            st.caption("Chưa hình thành kịch bản BUY/SELL rõ ràng.")

        # Chi tiết chấm điểm từng chỉ báo gom vào Expander cho gọn màn hình điện thoại
        with st.expander("🔎 Xem chi tiết điểm từng chỉ báo H1", expanded=False):
            st.write(f"{'✅' if gia_ht > ema_fast else '🔻'} Giá {'TRÊN' if gia_ht > ema_fast else 'DƯỚI'} EMA {cfg['ema_fast']} ({'+1' if gia_ht > ema_fast else '-1'})")
            st.write(f"{'✅' if ema_fast > ema_slow else '🔻'} EMA {cfg['ema_fast']} {'TRÊN' if ema_fast > ema_slow else 'DƯỚI'} EMA {cfg['ema_slow']} ({'+1' if ema_fast > ema_slow else '-1'})")
            st.write(f"{'✅' if gia_ht > sma_trend else '🔻'} Giá {'TRÊN' if gia_ht > sma_trend else 'DƯỚI'} SMA {cfg['sma_trend']} ({'+1' if gia_ht > sma_trend else '-1'})")
            if rsi > cfg["rsi_buy"]:
                st.write(f"✅ RSI = {rsi:.1f} (> {cfg['rsi_buy']}) (+1)")
            elif rsi < cfg["rsi_sell"]:
                st.write(f"🔻 RSI = {rsi:.1f} (< {cfg['rsi_sell']}) (-1)")
            else:
                st.write(f"⚖️ RSI = {rsi:.1f} (Trung tính {cfg['rsi_sell']}-{cfg['rsi_buy']}) (0)")
            st.write(f"{'✅' if macd_line > macd_signal else '🔻'} MACD ({cfg['macd_fast']},{cfg['macd_slow']},{cfg['macd_sig']}) {'TRÊN' if macd_line > macd_signal else 'DƯỚI'} Signal ({'+1' if macd_line > macd_signal else '-1'})")

# --- 6. GIAO DIỆN CHÍNH MOBILE-FIRST ---
data_init = load_data()

st.markdown("### 📱 Bot Trading Forex & Vàng")

# Thanh chọn cặp tiền ngay trên màn hình chính (1 chạm trên điện thoại)
pair_keys = list(PAIR_CONFIG.keys())
default_idx = pair_keys.index(data_init["selected_symbol"])
selected_symbol = st.selectbox(
    "Chọn cặp tiền giao dịch:",
    pair_keys,
    index=default_idx,
    label_visibility="collapsed"
)
if selected_symbol != data_init["selected_symbol"]:
    data_init["selected_symbol"] = selected_symbol
    save_data(data_init)

st.caption(f"📌 {PAIR_CONFIG[selected_symbol]['desc']}")

# Bảng cài đặt vốn & Auto-Refresh đặt ngay trên màn hình chính (lưu vĩnh viễn khi F5)
with st.expander("⚙️ Cài đặt Vốn, Auto-Refresh & Reset", expanded=False):
    c_set1, c_set2 = st.columns(2)
    with c_set1:
        auto_refresh = st.toggle("🔄 Auto-Refresh", value=bool(data_init["auto_refresh"]))
        if auto_refresh != data_init["auto_refresh"]:
            data_init["auto_refresh"] = auto_refresh
            save_data(data_init)
    with c_set2:
        refresh_map = {"60 giây": 60, "120 giây (2p)": 120, "300 giây (5p)": 300, "600 giây (10p)": 600}
        rev_map = {v: k for k, v in refresh_map.items()}
        cur_label = rev_map.get(data_init["refresh_sec"], "120 giây (2p)")
        ref_choice = st.selectbox("Chu kỳ quét:", list(refresh_map.keys()), index=list(refresh_map.keys()).index(cur_label))
        if refresh_map[ref_choice] != data_init["refresh_sec"]:
            data_init["refresh_sec"] = refresh_map[ref_choice]
            save_data(data_init)

    lot_input = st.number_input("⚖️ Khối lượng lệnh mới (Lot):", value=float(data_init["lot_size"]), step=0.01, format="%.2f")
    if lot_input != data_init["lot_size"]:
        data_init["lot_size"] = float(lot_input)
        save_data(data_init)

    reset_balance = st.number_input("💰 Số vốn ban đầu khi Reset ($):", value=float(data_init["initial_balance"]), step=100.0)
    if reset_balance != data_init["initial_balance"]:
        data_init["initial_balance"] = float(reset_balance)
        save_data(data_init)

    if st.button("🔄 Reset Toàn Bộ Tài Khoản", use_container_width=True):
        new_data = {
            "balance": float(reset_balance),
            "initial_balance": float(reset_balance),
            "lot_size": float(lot_input),
            "selected_symbol": selected_symbol,
            "auto_refresh": auto_refresh,
            "refresh_sec": data_init["refresh_sec"],
            "open_trades": {},
            "trade_history": []
        }
        save_data(new_data)
        st.success("Đã reset tài khoản thành công!")
        st.rerun()

# 3 Tab chính tối ưu cho thao tác trên điện thoại
tab1, tab2, tab3 = st.tabs(["📈 Phân Tích", "🚀 Radar 7 Cặp", "💼 Winrate & Lệnh"])

with tab1:
    if auto_refresh:
        st.caption(f"🟢 Tự động cập nhật mỗi **{data_init['refresh_sec']} giây** (Giờ VN).")

        @st.fragment(run_every=data_init["refresh_sec"])
        def mobile_auto_panel():
            hien_thi_phan_tich_chi_tiet(selected_symbol)

        mobile_auto_panel()
    else:
        if st.button(f"📡 Cập Nhật {selected_symbol} Ngay", type="primary", use_container_width=True):
            hien_thi_phan_tich_chi_tiet(selected_symbol)
        else:
            st.info("Bấm nút phía trên để tải giá mới nhất hoặc bật Auto-Refresh trong mục Cài đặt.")

with tab2:
    if st.button("🚀 Quét Tất Cả 7 Cặp (Tìm Entry Đẹp)", type="primary", use_container_width=True):
        quet_tat_ca_cap_tien()

    if "scan_all_table" in st.session_state:
        st.caption(f"🕒 Quét toàn bộ lúc: **{st.session_state['scan_all_time']}**")

        for loai, msg in st.session_state.get("scan_all_alerts", []):
            if loai == "success":
                st.success(msg)
            else:
                st.info(msg)

        best_list = st.session_state.get("scan_all_best", [])
        if len(best_list) > 0:
            st.success(f"🌟 Có **{len(best_list)} cặp** đạt Entry đẹp 100%:")
            for b in best_list:
                icon = "🟢" if "BUY" in b["kich_ban"] else "🔴"
                c_cls = "trade-buy" if "BUY" in b["kich_ban"] else "trade-sell"
                st.markdown(f"""
                <div class="trade-card {c_cls}">
                    <div><b>{icon} {b['symbol']} — {b['kich_ban']}</b> (Điểm: <code>{b['diem']:+d}/5</code> | ADX: <code>{b['adx']}</code>)</div>
                    <div>📍 Entry: <code>{b['entry']}</code></div>
                    <div>🎯 TP: <code>{b['tp']}</code> | 🛑 SL: <code>{b['sl']}</code></div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("⏳ Chưa có cặp nào đạt đủ 100% điều kiện Entry đẹp.")

        st.dataframe(pd.DataFrame(st.session_state["scan_all_table"]), use_container_width=True, hide_index=True)
    else:
        st.info("Bấm nút màu đỏ phía trên để quét nhanh toàn bộ 7 cặp tiền và lọc ra điểm vào đẹp nhất.")

with tab3:
    hien_thi_thong_ke(load_data())
