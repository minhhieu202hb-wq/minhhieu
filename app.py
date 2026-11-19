import streamlit as st
import pandas as pd
import requests
import json
import os
import datetime

st.set_page_config(page_title="Bot Phân Tích & Giao Dịch Ảo Đa Cặp Tiền", layout="wide")

DATA_FILE = "trading_data.json"
VN_TZ = datetime.timezone(datetime.timedelta(hours=7))

# --- CẤU HÌNH QUY CHUẨN TỪNG CẶP TIỀN ---
PAIR_CONFIG = {
    "XAU/USD": {"contract_size": 100,    "decimals": 2, "usd_base": False, "sl_mult": 1.5, "tp_mult": 3.0},
    "EUR/USD": {"contract_size": 100000, "decimals": 5, "usd_base": False, "sl_mult": 1.5, "tp_mult": 3.0},
    "GBP/USD": {"contract_size": 100000, "decimals": 5, "usd_base": False, "sl_mult": 1.5, "tp_mult": 3.0},
    "AUD/USD": {"contract_size": 100000, "decimals": 5, "usd_base": False, "sl_mult": 1.5, "tp_mult": 3.0},
    "USD/JPY": {"contract_size": 100000, "decimals": 3, "usd_base": True,  "sl_mult": 1.5, "tp_mult": 3.0},
    "USD/CHF": {"contract_size": 100000, "decimals": 5, "usd_base": True,  "sl_mult": 1.5, "tp_mult": 3.0},
    "USD/CAD": {"contract_size": 100000, "decimals": 5, "usd_base": True,  "sl_mult": 1.5, "tp_mult": 3.0},
    "BTC/USD": {"contract_size": 1,      "decimals": 2, "usd_base": False, "sl_mult": 2.0, "tp_mult": 4.0},
}

def gio_vn_hien_tai():
    return datetime.datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S (VN)")

# --- 1. LƯU & ĐỌC DỮ LIỆU TỪ FILE JSON (KHÔNG BỊ RESET KHI THOÁT WEB) ---
def load_data():
    default_data = {
        "balance": 1000.0,
        "initial_balance": 1000.0,  # Thêm dòng này để nhớ mức vốn khi F5
        "lot_size": 0.01,
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

def phan_tich_ky_thuat(df):
    df["EMA_21"] = df["Close"].ewm(span=21, adjust=False).mean()
    df["EMA_89"] = df["Close"].ewm(span=89, adjust=False).mean()
    df["SMA_200"] = df["Close"].rolling(window=200).mean()

    df["BB_Mid"] = df["Close"].rolling(window=20).mean()
    df["BB_Std"] = df["Close"].rolling(window=20).std()
    df["BB_Up"] = df["BB_Mid"] + (df["BB_Std"] * 2)
    df["BB_Low"] = df["BB_Mid"] - (df["BB_Std"] * 2)

    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean().replace(0, 1e-10)
    df["RSI_14"] = 100 - (100 / (1 + (gain / loss)))

    df["MACD"] = df["Close"].ewm(span=12, adjust=False).mean() - df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    true_range = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift()).abs(),
        (df["Low"] - df["Close"].shift()).abs()
    ], axis=1).max(axis=1)
    df["ATR_14"] = true_range.rolling(14).mean()

    df["Bullish_Score"] = 0
    df.loc[df["Close"] > df["EMA_21"], "Bullish_Score"] += 1
    df.loc[df["Close"] <= df["EMA_21"], "Bullish_Score"] -= 1
    df.loc[df["EMA_21"] > df["EMA_89"], "Bullish_Score"] += 1
    df.loc[df["EMA_21"] <= df["EMA_89"], "Bullish_Score"] -= 1
    df.loc[df["Close"] > df["SMA_200"], "Bullish_Score"] += 1
    df.loc[df["Close"] <= df["SMA_200"], "Bullish_Score"] -= 1
    df.loc[df["RSI_14"] > 55, "Bullish_Score"] += 1
    df.loc[df["RSI_14"] < 45, "Bullish_Score"] -= 1
    df.loc[df["MACD"] > df["MACD_Signal"], "Bullish_Score"] += 1
    df.loc[df["MACD"] <= df["MACD_Signal"], "Bullish_Score"] -= 1

    return df.dropna().reset_index(drop=True)

def danh_gia_tin_hieu(df_ptkt, symbol):
    cfg = PAIR_CONFIG[symbol]
    nen_ht = df_ptkt.iloc[-1]
    gia_ht = nen_ht["Close"]
    ema_21 = nen_ht["EMA_21"]
    bb_up = nen_ht["BB_Up"]
    bb_low = nen_ht["BB_Low"]
    atr = nen_ht["ATR_14"]
    diem = int(nen_ht["Bullish_Score"])

    sl_khoang = atr * cfg["sl_mult"]
    tp_khoang = atr * cfg["tp_mult"]

    kich_ban = "BUY (LONG)" if diem >= 3 else ("SELL (SHORT)" if diem <= -3 else "ĐỨNG NGOÀI")
    dk1 = dk2 = dk3 = False

    if kich_ban == "BUY (LONG)":
        dk1 = diem >= 4
        dk2 = gia_ht < bb_up
        dk3 = abs(gia_ht - ema_21) <= (atr * 0.8)
    elif kich_ban == "SELL (SHORT)":
        dk1 = diem <= -4
        dk2 = gia_ht > bb_low
        dk3 = abs(ema_21 - gia_ht) <= (atr * 0.8)

    dieu_kien_vao_lenh = dk1 and dk2 and dk3
    so_dk_dat = int(dk1) + int(dk2) + int(dk3)

    return {
        "nen_ht": nen_ht,
        "gia_ht": gia_ht,
        "ema_21": ema_21,
        "ema_89": nen_ht["EMA_89"],
        "sma_200": nen_ht["SMA_200"],
        "rsi": nen_ht["RSI_14"],
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

    # A. Kiểm tra chốt lệnh đang mở của cặp này
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
            thong_bao.append(("success", f"🔔 Tự động CHỐT LỆNH {symbol} ({trade['Type']}) do {li_do}. PnL: {pnl:+.2f} USD"))
        else:
            save_data(data)

    # B. Tự động mở lệnh mới nếu đạt 100% kịch bản lý tưởng
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
            thong_bao.append(("info", f"🔔 Bot đã tự động VÀO LỆNH BUY {symbol} tại {gia_ht:.{dec}f}"))
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
            thong_bao.append(("info", f"🔔 Bot đã tự động VÀO LỆNH SELL {symbol} tại {gia_ht:.{dec}f}"))

    return thong_bao

# --- 3. HÀM QUÉT TOÀN BỘ 8 CẶP & GỢI Ý ENTRY ĐẸP ---
def quet_tat_ca_cap_tien():
    data = load_data()
    ket_qua_tong_hop = []
    entry_dep_list = []
    tat_ca_thong_bao = []
    symbols = list(PAIR_CONFIG.keys())

    progress = st.progress(0, text="Đang bắt đầu quét toàn bộ danh sách cặp tiền...")
    for idx, sym in enumerate(symbols):
        progress.progress((idx + 1) / len(symbols), text=f"Đang quét {sym} ({idx + 1}/{len(symbols)})...")
        df_raw = lay_du_lieu_h1(sym, show_error=False)
        if df_raw is None:
            ket_qua_tong_hop.append({
                "Cặp tiền": sym,
                "Giá hiện tại": "Lỗi API",
                "Điểm Trend": "-",
                "Kịch bản": "-",
                "Đánh giá Entry": "⚠️ Quá giới hạn API (Đợi 1 phút)",
                "SL gợi ý": "-",
                "TP gợi ý": "-",
                "Ưu tiên": 3
            })
            continue

        df_ptkt = phan_tich_ky_thuat(df_raw)
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
            danh_gia = "🌟 ENTRY ĐẸP (Đạt 3/3)"
            uu_tien = 0
            entry_dep_list.append({
                "symbol": sym,
                "kich_ban": kq["kich_ban"],
                "entry": f"{gia:.{dec}f}",
                "sl": sl_val,
                "tp": tp_val,
                "diem": kq["diem"]
            })
        elif kq["kich_ban"] != "ĐỨNG NGOÀI" and kq["so_dk_dat"] == 2:
            danh_gia = "⏳ Đợi hồi / Gần đẹp (2/3)"
            uu_tien = 1
        elif kq["kich_ban"] != "ĐỨNG NGOÀI":
            danh_gia = f"🔎 Có xu hướng ({kq['so_dk_dat']}/3)"
            uu_tien = 2
        else:
            danh_gia = "⚪ Đi ngang (Đứng ngoài)"
            uu_tien = 3

        ket_qua_tong_hop.append({
            "Cặp tiền": sym,
            "Giá hiện tại": f"{gia:.{dec}f}",
            "Điểm Trend": f"{kq['diem']:+d}/5",
            "Kịch bản": kq["kich_ban"],
            "Đánh giá Entry": danh_gia,
            "SL gợi ý": sl_val,
            "TP gợi ý": tp_val,
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

# --- 4. HÀM HIỂN THỊ THỐNG KÊ TÀI KHOẢN & WINRATE ---
def hien_thi_thong_ke(data):
    st.header("💼 Quản Lý Giao Dịch & Thống Kê Winrate")

    tong_live_pnl = 0.0
    for sym, t in data["open_trades"].items():
        gia_tham_chieu = t.get("Last_Price", t["Entry"])
        tong_live_pnl += tinh_pnl(sym, t["Type"], t["Entry"], gia_tham_chieu, t["Lot"])

    equity = data["balance"] + tong_live_pnl
    lich_su = data["trade_history"]
    tong_lenh = len(lich_su)
    lenh_thang = sum(1 for l in lich_su if "TP" in l["Lý do"])
    lenh_thua = tong_lenh - lenh_thang
    winrate = (lenh_thang / tong_lenh * 100) if tong_lenh > 0 else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Số dư (Balance)", f"${data['balance']:,.2f}")
    m2.metric("Vốn thực (Equity)", f"${equity:,.2f}", f"{tong_live_pnl:+.2f} USD (Đang chạy)")
    m3.metric("Winrate (%)", f"{winrate:.1f}%", f"{lenh_thang} Thắng / {lenh_thua} Thua")
    m4.metric("Tổng Lệnh Đã Chốt", tong_lenh)

    col_trai, col_phai = st.columns([1, 1.6])

    with col_trai:
        st.subheader(f"🎯 Các Lệnh Đang Chạy ({len(data['open_trades'])})")
        if len(data["open_trades"]) > 0:
            for sym, t in data["open_trades"].items():
                d = PAIR_CONFIG[sym]["decimals"]
                gia_ht_sym = t.get("Last_Price", t["Entry"])
                pnl_sym = tinh_pnl(sym, t["Type"], t["Entry"], gia_ht_sym, t["Lot"])
                icon = "🟢" if t["Type"] == "BUY" else "🔴"
                st.markdown(f"""
                **{icon} {sym} — {t['Type']} ({t['Lot']} Lot)**
                * Mở lúc (VN): `{t['Time']}`
                * Entry: `{t['Entry']:.{d}f}` | Giá mới nhất: `{gia_ht_sym:.{d}f}`
                * TP: `{t['TP']:.{d}f}` | SL: `{t['SL']:.{d}f}`
                * PnL tạm tính: **`{pnl_sym:+.2f} USD`**
                """)
                st.markdown("---")
        else:
            st.write("⚪ *Hiện chưa có lệnh nào đang mở.*")

    with col_phai:
        st.subheader("📝 Sao Kê Lịch Sử Đã Chốt")
        if tong_lenh > 0:
            st.dataframe(pd.DataFrame(lich_su).iloc[::-1], use_container_width=True, hide_index=True)
        else:
            st.write("Chưa có lệnh nào được chốt để tính Winrate.")

# --- 5. HÀM QUÉT CHI TIẾT 1 CẶP TIỀN ---
def quet_va_xu_ly(symbol):
    data = load_data()
    dec = PAIR_CONFIG[symbol]["decimals"]
    gio_quet = gio_vn_hien_tai()

    with st.spinner(f"Đang tải dữ liệu H1 của {symbol}..."):
        df_raw = lay_du_lieu_h1(symbol)

    if df_raw is not None:
        df_ptkt = phan_tich_ky_thuat(df_raw)
        if len(df_ptkt) == 0:
            st.error("Chưa đủ 200 nến để tính SMA 200. Vui lòng thử lại sau.")
        else:
            kq = danh_gia_tin_hieu(df_ptkt, symbol)
            nen_ht = kq["nen_ht"]
            gia_ht = kq["gia_ht"]
            ema_21 = kq["ema_21"]
            ema_89 = kq["ema_89"]
            sma_200 = kq["sma_200"]
            rsi = kq["rsi"]
            macd_line = kq["macd_line"]
            macd_signal = kq["macd_signal"]
            bb_up = kq["bb_up"]
            bb_low = kq["bb_low"]
            atr = kq["atr"]
            diem = kq["diem"]

            # PHẦN 1: BẢNG ĐIỀU KHIỂN KỸ THUẬT
            st.header(f"📈 Phân Tích Chi Tiết {symbol}")
            st.caption(f"🕒 Quét lúc: **{gio_quet}** | Nến H1 (Giờ VN): `{nen_ht['Date']}`")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Giá Hiện Tại", f"{gia_ht:.{dec}f}")
            c2.metric("EMA 21 / EMA 89", f"{ema_21:.{dec}f}", f"EMA89: {ema_89:.{dec}f}")
            c3.metric("SMA 200 (Cản cứng)", f"{sma_200:.{dec}f}")
            c4.metric("RSI (14) / ATR (14)", f"{rsi:.1f}", f"ATR: {atr:.{dec}f}")

            st.markdown("---")
            col_pt, col_cl, col_check = st.columns(3)

            with col_pt:
                st.subheader("🔎 Phân Tích Cấu Trúc H1")
                st.write("✅ Giá nằm TRÊN EMA 21 (+1)" if gia_ht > ema_21 else "🔻 Giá nằm DƯỚI EMA 21 (-1)")
                st.write("✅ EMA 21 cắt LÊN EMA 89 (+1)" if ema_21 > ema_89 else "🔻 EMA 21 cắt XUỐNG EMA 89 (-1)")
                st.write("✅ Giá nằm TRÊN SMA 200 (+1)" if gia_ht > sma_200 else "🔻 Giá nằm DƯỚI SMA 200 (-1)")
                if rsi > 55:
                    st.write(f"✅ RSI = {rsi:.1f} (> 55) (+1)")
                elif rsi < 45:
                    st.write(f"🔻 RSI = {rsi:.1f} (< 45) (-1)")
                else:
                    st.write(f"⚖️ RSI = {rsi:.1f} (Đi ngang 45-55) (0)")
                st.write("✅ MACD cắt LÊN Signal (+1)" if macd_line > macd_signal else "🔻 MACD cắt XUỐNG Signal (-1)")
                st.markdown(f"**Tổng điểm xu hướng:** `{diem:+d} / 5`")

            with col_cl:
                st.subheader("🎯 Chiến Lược Khuyến Nghị")
                if diem >= 3:
                    st.success("🔥 **XU HƯỚNG CHÍNH: TĂNG MẠNH (UPTREND)**")
                    st.markdown(
                        f"🟢 **KHUYẾN NGHỊ: BUY (LONG)** \n"
                        f"* **Entry tham khảo:** `{gia_ht:.{dec}f}` (hoặc hồi về `{ema_21:.{dec}f}`) \n"
                        f"* **Take Profit:** `{gia_ht + kq['tp_khoang']:.{dec}f}` \n"
                        f"* **Stop Loss:** `{gia_ht - kq['sl_khoang']:.{dec}f}`"
                    )
                elif diem <= -3:
                    st.error("📉 **XU HƯỚNG CHÍNH: GIẢM MẠNH (DOWNTREND)**")
                    st.markdown(
                        f"🔴 **KHUYẾN NGHỊ: SELL (SHORT)** \n"
                        f"* **Entry tham khảo:** `{gia_ht:.{dec}f}` (hoặc hồi về `{ema_21:.{dec}f}`) \n"
                        f"* **Take Profit:** `{gia_ht - kq['tp_khoang']:.{dec}f}` \n"
                        f"* **Stop Loss:** `{gia_ht + kq['sl_khoang']:.{dec}f}`"
                    )
                else:
                    st.warning("⚖️ **XU HƯỚNG CHÍNH: ĐI NGANG (SIDEWAYS)**")
                    st.markdown("⚪ **KHUYẾN NGHỊ: ĐỨNG NGOÀI** \n* Các chỉ báo đang mâu thuẫn, chưa có điểm vào an toàn.")

            with col_check:
                st.subheader("📋 Checklist Kịch Bản Lí Tưởng")
                st.write(f"Kịch bản theo dõi: **{kq['kich_ban']}**")

                def ve_tich(dk):
                    return "✅" if dk else "⬜"

                if kq["kich_ban"] == "BUY (LONG)":
                    st.markdown(f"""
                    * {ve_tich(kq['dk1'])} **Đồng thuận mạnh:** Đạt ít nhất 4/5 điểm TĂNG.
                    * {ve_tich(kq['dk2'])} **Không FOMO:** Giá dưới biên trên BB (`{bb_up:.{dec}f}`).
                    * {ve_tich(kq['dk3'])} **Vị thế an toàn:** Giá gần EMA 21 (`{ema_21:.{dec}f}`).
                    """)
                    if kq["dieu_kien_vao_lenh"]:
                        st.success("🎉 Đạt đủ 100% điều kiện kịch bản lí tưởng!")
                    else:
                        st.info("⏳ Chưa đủ điều kiện lí tưởng, đang đợi giá hồi.")
                elif kq["kich_ban"] == "SELL (SHORT)":
                    st.markdown(f"""
                    * {ve_tich(kq['dk1'])} **Đồng thuận mạnh:** Đạt ít nhất 4/5 điểm GIẢM.
                    * {ve_tich(kq['dk2'])} **Không FOMO:** Giá trên biên dưới BB (`{bb_low:.{dec}f}`).
                    * {ve_tich(kq['dk3'])} **Vị thế an toàn:** Giá gần EMA 21 (`{ema_21:.{dec}f}`).
                    """)
                    if kq["dieu_kien_vao_lenh"]:
                        st.success("🎉 Đạt đủ 100% điều kiện kịch bản lí tưởng!")
                    else:
                        st.info("⏳ Chưa đủ điều kiện lí tưởng, đang đợi giá hồi.")
                else:
                    st.info("⚪ Thị trường đi ngang, tạm đứng ngoài quan sát.")

            st.markdown("---")

            # PHẦN 2: XỬ LÝ LỆNH ẢO
            thong_bao = xu_ly_lenh_ao(data, symbol, kq)
            for loai, msg in thong_bao:
                if loai == "success":
                    st.success(msg)
                else:
                    st.info(msg)

    # PHẦN 3: THỐNG KÊ TÀI KHOẢN & WINRATE
    hien_thi_thong_ke(data)

# --- 6. SIDEBAR ĐIỀU KHIỂN ---
data_init = load_data()

st.sidebar.header("🌐 Chọn Cặp Tiền Chi Tiết")
selected_symbol = st.sidebar.selectbox("Danh sách cặp tiền:", list(PAIR_CONFIG.keys()), index=0)

st.sidebar.markdown("---")
st.sidebar.header("⚡ Chế Độ Chạy Liên Tục")
auto_refresh = st.sidebar.toggle("🔄 Tự động cập nhật cặp đang chọn", value=True)
refresh_options = {
    "60 giây (Nhanh - tốn API)": 60,
    "120 giây (Khuyên dùng 24/24)": 120,
    "300 giây (5 phút - Tiết kiệm)": 300,
    "600 giây (10 phút)": 600
}
refresh_label = st.sidebar.selectbox("Chu kỳ cập nhật:", list(refresh_options.keys()), index=1)
refresh_sec = refresh_options[refresh_label]

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Quản Lý Vốn (Tự động lưu)")
lot_input = st.sidebar.number_input("⚖️ Khối lượng cho lệnh mới (Lot)", value=float(data_init["lot_size"]), step=0.01, format="%.2f")
if lot_input != data_init["lot_size"]:
    data_init["lot_size"] = lot_input
    save_data(data_init)

st.sidebar.markdown("---")
st.sidebar.subheader("⚠️ Đặt lại tài khoản")
reset_balance = st.sidebar.number_input("💰 Số vốn ban đầu khi Reset ($)", value=1000.0, step=100.0)
if st.sidebar.button("🔄 Reset Toàn Bộ Tài Khoản"):
    new_data = {
        "balance": float(reset_balance),
        "lot_size": float(lot_input),
        "open_trades": {},
        "trade_history": []
    }
    save_data(new_data)
    st.sidebar.success("Đã reset tài khoản thành công!")
    st.rerun()

# --- 7. GIAO DIỆN CHÍNH ---
st.title(f"🥇 Bot Phân Tích & Giao Dịch Ảo Đa Cặp Tiền")

# KHU VỰC QUÉT TẤT CẢ & GỢI Ý ENTRY ĐẸP
if st.button("🚀 Quét & Cập Nhật Tất Cả 8 Cặp Tiền (Tìm Entry Đẹp)", type="primary", use_container_width=True):
    quet_tat_ca_cap_tien()

if "scan_all_table" in st.session_state:
    st.subheader(f"🔍 Radar Quét Thị Trường — Cập nhật lúc {st.session_state['scan_all_time']}")

    for loai, msg in st.session_state.get("scan_all_alerts", []):
        if loai == "success":
            st.success(msg)
        else:
            st.info(msg)

    best_list = st.session_state.get("scan_all_best", [])
    if len(best_list) > 0:
        st.success(f"🌟 **Phát hiện {len(best_list)} cặp đang có ENTRY ĐẸP (Đạt 100% Checklist):**")
        for b in best_list:
            icon = "🟢" if "BUY" in b["kich_ban"] else "🔴"
            st.markdown(
                f"* {icon} **{b['symbol']} — {b['kich_ban']}** (Điểm: `{b['diem']:+d}/5`) | "
                f"Entry: `{b['entry']}` | SL: `{b['sl']}` | TP: `{b['tp']}`"
            )
    else:
        st.warning("⏳ Hiện chưa có cặp nào đạt đủ 100% điều kiện Entry đẹp. Xem các cặp `Gần đẹp (2/3)` bên dưới để canh nhịp hồi.")

    st.dataframe(pd.DataFrame(st.session_state["scan_all_table"]), use_container_width=True, hide_index=True)
    st.markdown("---")

# KHU VỰC PHÂN TÍCH CHI TIẾT CẶP ĐANG CHỌN
if auto_refresh:
    st.success(f"🟢 Đang tự động theo dõi **{selected_symbol}** mỗi **{refresh_sec} giây** (Giờ VN).")

    @st.fragment(run_every=refresh_sec)
    def auto_run_panel():
        quet_va_xu_ly(selected_symbol)

    auto_run_panel()
else:
    st.info("⚪ Chế độ tự động đang TẮT. Bấm nút bên dưới để cập nhật thủ công hoặc bật Auto-Refresh ở cột trái.")
    if st.button(f"📡 Cập Nhật Giá {selected_symbol} & Chạy Bot", use_container_width=True):
        quet_va_xu_ly(selected_symbol)
    else:
        hien_thi_thong_ke(load_data())
