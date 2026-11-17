import streamlit as st
import pandas as pd
import requests
import datetime

st.set_page_config(page_title="Bot Giao Dịch Ảo XAU/USD (Pro)", layout="wide")

# --- 1. KHỞI TẠO BỘ NHỚ LƯU TRỮ ---
if 'balance' not in st.session_state:
    st.session_state.balance = 1000.0
if 'open_trade' not in st.session_state:
    st.session_state.open_trade = None
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'lot_size' not in st.session_state:
    st.session_state.lot_size = 0.01

def reset_account(new_bal, new_lot):
    st.session_state.balance = new_bal
    st.session_state.lot_size = new_lot
    st.session_state.open_trade = None
    st.session_state.trade_history = []

# --- 2. CẤU HÌNH SIDEBAR ---
st.sidebar.header("⚙️ Quản Lý Vốn")
new_balance = st.sidebar.number_input("💰 Số vốn ban đầu ($)", value=1000.0, step=100.0)
new_lot = st.sidebar.number_input("⚖️ Khối lượng lệnh (Lot)", value=0.01, step=0.01)

if st.sidebar.button("🔄 Reset Tài Khoản"):
    reset_account(new_balance, new_lot)
    st.sidebar.success("Đã reset tài khoản!")

# --- 3. LẤY DỮ LIỆU & PHÂN TÍCH KỸ THUẬT (TỐI ƯU CHO VÀNG) ---
def lay_du_lieu_vang_h1():
    api_key = "05c4ba66953c4eb79030baf0da24f012"
    # Tăng outputsize lên 300 để có đủ nến tính SMA 200
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1h&outputsize=300&apikey={api_key}"
    try:
        res = requests.get(url).json()
        if 'values' in res:
            df = pd.DataFrame(res['values']).iloc[::-1].reset_index(drop=True)
            for col in ['open', 'high', 'low', 'close']:
                df[col] = df[col].astype(float)
            df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'datetime': 'Date'}, inplace=True)
            return df
        return None
    except:
        return None

def phan_tich_ky_thuat(df):
    # 1. Các đường MA Fibonacci & Dài hạn
    df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['EMA_89'] = df['Close'].ewm(span=89, adjust=False).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    
    # 2. Bollinger Bands (20, 2) - Ngăn chặn FOMO đu đỉnh/đáy
    df['BB_Mid'] = df['Close'].rolling(window=20).mean()
    df['BB_Std'] = df['Close'].rolling(window=20).std()
    df['BB_Up'] = df['BB_Mid'] + (df['BB_Std'] * 2)
    df['BB_Low'] = df['BB_Mid'] - (df['BB_Std'] * 2)

    # 3. RSI 14 (Chuẩn mực)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI_14'] = 100 - (100 / (1 + (gain / loss)))
    
    # 4. MACD (12, 26, 9)
    df['MACD'] = df['Close'].ewm(span=12, adjust=False).mean() - df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # 5. ATR 14 (Tính toán SL/TP)
    true_range = pd.concat([df['High'] - df['Low'], (df['High'] - df['Close'].shift()).abs(), (df['Low'] - df['Close'].shift()).abs()], axis=1).max(axis=1)
    df['ATR_14'] = true_range.rolling(14).mean()
    
    # CHẤM ĐIỂM XU HƯỚNG TỔNG HỢP (Tối đa 5 điểm)
    df['Bullish_Score'] = 0
    # Tiêu chí 1: Nến hiện tại so với EMA 21
    df.loc[df['Close'] > df['EMA_21'], 'Bullish_Score'] += 1
    df.loc[df['Close'] <= df['EMA_21'], 'Bullish_Score'] -= 1
    # Tiêu chí 2: Cấu trúc trung hạn (Fibonacci Cross)
    df.loc[df['EMA_21'] > df['EMA_89'], 'Bullish_Score'] += 1
    df.loc[df['EMA_21'] <= df['EMA_89'], 'Bullish_Score'] -= 1
    # Tiêu chí 3: Cấu trúc dài hạn (Phễu lọc tổ chức)
    df.loc[df['Close'] > df['SMA_200'], 'Bullish_Score'] += 1
    df.loc[df['Close'] <= df['SMA_200'], 'Bullish_Score'] -= 1
    # Tiêu chí 4: Động lượng (RSI phải > 55 mới thực sự tăng, < 45 mới giảm)
    df.loc[df['RSI_14'] > 55, 'Bullish_Score'] += 1
    df.loc[df['RSI_14'] < 45, 'Bullish_Score'] -= 1
    # Tiêu chí 5: MACD
    df.loc[df['MACD'] > df['MACD_Signal'], 'Bullish_Score'] += 1
    df.loc[df['MACD'] <= df['MACD_Signal'], 'Bullish_Score'] -= 1
    
    return df.dropna().reset_index(drop=True)

# --- 4. GIAO DIỆN CHÍNH ---
st.title("🥇 Bot Pro: Giao Dịch Ảo XAU/USD (Fibonacci & BB)")

if st.button("📡 Cập Nhật Giá & Chạy Bot", type="primary", use_container_width=True):
    with st.spinner("Đang tải dữ liệu H1 và áp dụng cấu trúc Fibonacci..."):
        df_vang = lay_du_lieu_vang_h1()
        if df_vang is not None:
            df_ptkt = phan_tich_ky_thuat(df_vang)
            if len(df_ptkt) == 0:
                st.error("Chưa đủ dữ liệu để tạo SMA 200. Vui lòng thử lại sau.")
            else:
                nen_ht = df_ptkt.iloc[-1]
                
                gia_ht = nen_ht['Close']
                ema_21 = nen_ht['EMA_21']
                ema_89 = nen_ht['EMA_89']
                sma_200 = nen_ht['SMA_200']
                rsi = nen_ht['RSI_14']
                macd_line = nen_ht['MACD']
                macd_signal = nen_ht['MACD_Signal']
                bb_up = nen_ht['BB_Up']
                bb_low = nen_ht['BB_Low']
                atr = nen_ht['ATR_14']
                diem = nen_ht['Bullish_Score']
                
                # =========================================================
                # PHẦN 1: BẢNG ĐIỀU KHIỂN KỸ THUẬT VÀNG
                # =========================================================
                st.header(f"📈 Phân Tích Kỹ Thuật (Cập nhật: {nen_ht['Date']})")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Giá Hiện Tại", f"{gia_ht:.2f}")
                c2.metric("SMA 200 (Cản cứng)", f"{sma_200:.2f}")
                c3.metric("RSI (14)", f"{rsi:.1f}")
                c4.metric("ATR (Độ biến động)", f"{atr:.2f}")
                
                st.markdown("---")
                col_pt, col_th = st.columns(2)
                
                with col_pt:
                    st.subheader("🔎 Điểm Chấm Cấu Trúc Khung H1")
                    st.write(f"{'✅' if gia_ht > ema_21 else '🔻'} **Giao dịch ngắn hạn:** Giá {'TRÊN' if gia_ht > ema_21 else 'DƯỚI'} EMA 21")
                    st.write(f"{'✅' if ema_21 > ema_89 else '🔻'} **Sóng trung hạn:** EMA 21 {'nằm TRÊN' if ema_21 > ema_89 else 'nằm DƯỚI'} EMA 89")
                    st.write(f"{'✅' if gia_ht > sma_200 else '🔻'} **Xu hướng vĩ mô:** Giá {'TRÊN' if gia_ht > sma_200 else 'DƯỚI'} SMA 200")
                    st.write(f"{'✅' if rsi > 55 else ('🔻' if rsi < 45 else '⚖️')} **Động lượng (RSI):** {rsi:.1f} {'(Tăng)' if rsi > 55 else ('(Giảm)' if rsi < 45 else '(Đi ngang)')}")
                    st.write(f"{'✅' if macd_line > macd_signal else '🔻'} **Dòng tiền (MACD):** {'Ủng hộ TĂNG' if macd_line > macd_signal else 'Ủng hộ GIẢM'}")

                sl_khoang = atr * 1.5
                tp_khoang = atr * 3.0
                
                with col_th:
                    st.subheader("📋 Checklist Lí Tưởng & Bộ Lọc FOMO")
                    
                    kich_ban = "BUY (LONG)" if diem >= 3 else ("SELL (SHORT)" if diem <= -3 else "ĐỨNG NGOÀI")
                    st.write(f"Kịch bản ưu tiên: **{kich_ban}**")
                    
                    def ve_tich(dk): return "✅" if dk else "⬜"
                    
                    if kich_ban == "BUY (LONG)":
                        dk1 = diem >= 4 # Xu hướng rất rõ ràng (đạt ít nhất 4/5 điểm)
                        dk2 = gia_ht < bb_up # Giá chưa chạm đỉnh băng trên (Không đu đỉnh)
                        dk3 = (gia_ht - ema_21) < (atr * 0.8) # Giá đang ở gần vùng mua EMA 21
                        st.markdown(f"""
                        * {ve_tich(dk1)} **Đồng thuận:** Có ít nhất 4 tín hiệu ủng hộ TĂNG.
                        * {ve_tich(dk2)} **Không FOMO:** Giá chưa chạm biên trên Bollinger Bands (`{bb_up:.2f}`).
                        * {ve_tich(dk3)} **Entry an toàn:** Giá đang ở gần dải hỗ trợ EMA 21 (`{ema_21:.2f}`).
                        """)
                        dieu_kien_vao_lenh = dk1 and dk2 and dk3
                        
                    elif kich_ban == "SELL (SHORT)":
                        dk1 = diem <= -4 
                        dk2 = gia_ht > bb_low # Giá chưa rớt khỏi đáy băng dưới (Không bán đáy)
                        dk3 = (ema_21 - gia_ht) < (atr * 0.8) 
                        st.markdown(f"""
                        * {ve_tich(dk1)} **Đồng thuận:** Có ít nhất 4 tín hiệu ủng hộ GIẢM.
                        * {ve_tich(dk2)} **Không FOMO:** Giá chưa chạm biên dưới Bollinger Bands (`{bb_low:.2f}`).
                        * {ve_tich(dk3)} **Entry an toàn:** Giá đang ở gần dải kháng cự EMA 21 (`{ema_21:.2f}`).
                        """)
                        dieu_kien_vao_lenh = dk1 and dk2 and dk3
                    else:
                        st.info("Thị trường Sideways hoặc các chỉ báo mâu thuẫn. Không có kịch bản lý tưởng.")
                        dieu_kien_vao_lenh = False

                st.markdown("---")

                # =========================================================
                # PHẦN 2: LOGIC VÀO LỆNH ẢO & THỐNG KÊ WINRATE
                # =========================================================
                
                # A. Kiểm tra chốt lệnh đang mở
                if st.session_state.open_trade is not None:
                    trade = st.session_state.open_trade
                    dong_lenh = False
                    li_do = ""
                    gia_khop = 0
                    
                    if trade['Type'] == 'BUY':
                        if nen_ht['Low'] <= trade['SL']:
                            dong_lenh, li_do, gia_khop = True, "Chạm SL ❌", trade['SL']
                        elif nen_ht['High'] >= trade['TP']:
                            dong_lenh, li_do, gia_khop = True, "Chạm TP ✅", trade['TP']
                    elif trade['Type'] == 'SELL':
                        if nen_ht['High'] >= trade['SL']:
                            dong_lenh, li_do, gia_khop = True, "Chạm SL ❌", trade['SL']
                        elif nen_ht['Low'] <= trade['TP']:
                            dong_lenh, li_do, gia_khop = True, "Chạm TP ✅", trade['TP']
                    
                    if dong_lenh:
                        pnl = (gia_khop - trade['Entry']) * 100 * trade['Lot'] if trade['Type'] == 'BUY' else (trade['Entry'] - gia_khop) * 100 * trade['Lot']
                        st.session_state.balance += pnl
                        st.session_state.trade_history.append({
                            'Vào lúc': trade['Time'], 'Đóng lúc': nen_ht['Date'],
                            'Loại': trade['Type'], 'Giá Vào': trade['Entry'], 'Giá Khớp': gia_khop,
                            'Lý do': li_do, 'Lãi/Lỗ': round(pnl, 2), 'Số Dư': round(st.session_state.balance, 2)
                        })
                        st.success(f"🔔 CHỐT LỆNH {trade['Type']} do {li_do}. PnL: {pnl:+.2f} USD")
                        st.session_state.open_trade = None

                # B. Tự động mở lệnh mới nều vượt qua bộ lọc FOMO
                if st.session_state.open_trade is None and dieu_kien_vao_lenh:
                    if kich_ban == "BUY (LONG)":
                        st.session_state.open_trade = {
                            'Time': nen_ht['Date'], 'Type': 'BUY', 'Lot': st.session_state.lot_size,
                            'Entry': gia_ht, 'SL': gia_ht - sl_khoang, 'TP': gia_ht + tp_khoang
                        }
                        st.info(f"🔔 Bot đã VÀO LỆNH BUY tại {gia_ht:.2f}")
                    elif kich_ban == "SELL (SHORT)":
                        st.session_state.open_trade = {
                            'Time': nen_ht['Date'], 'Type': 'SELL', 'Lot': st.session_state.lot_size,
                            'Entry': gia_ht, 'SL': gia_ht + sl_khoang, 'TP': gia_ht - tp_khoang
                        }
                        st.info(f"🔔 Bot đã VÀO LỆNH SELL tại {gia_ht:.2f}")

                # C. Hiển thị Bảng Thống Kê
                st.header("💼 Quản Lý Giao Dịch & Sao Kê")
                live_pnl = 0.0
                if st.session_state.open_trade:
                    t = st.session_state.open_trade
                    live_pnl = (gia_ht - t['Entry']) * 100 * t['Lot'] if t['Type'] == 'BUY' else (t['Entry'] - gia_ht) * 100 * t['Lot']
                equity = st.session_state.balance + live_pnl

                lich_su = st.session_state.trade_history
                tong_lenh = len(lich_su)
                lenh_thang = sum(1 for l in lich_su if "TP" in l['Lý do'])
                lenh_thua = tong_lenh - lenh_thang
                winrate = (lenh_thang / tong_lenh * 100) if tong_lenh > 0 else 0

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Số dư (Balance)", f"${st.session_state.balance:,.2f}")
                c2.metric("Vốn thực (Equity)", f"${equity:,.2f}", f"{live_pnl:+.2f} (Live PnL)")
                c3.metric("Winrate (%)", f"{winrate:.1f}%", f"{lenh_thang} W / {lenh_thua} L")
                c4.metric("Tổng Lệnh", tong_lenh)
                
                col_trai, col_phai = st.columns([1, 1.5])
                with col_trai:
                    st.subheader("🎯 Vị Thế Đang Mở")
                    if st.session_state.open_trade:
                        t = st.session_state.open_trade
                        color = "🟢" if t['Type'] == 'BUY' else "🔴"
                        st.markdown(f"""
                        **{color} {t['Type']} ({t['Lot']} Lot)**
                        * **Entry:** `{t['Entry']:.2f}`
                        * **TP:** `{t['TP']:.2f}` | **SL:** `{t['SL']:.2f}`
                        * **Live PnL:** `{live_pnl:+.2f} USD`
                        """)
                    else:
                        st.write("⚪ *Đang đợi tín hiệu hội tụ hoàn hảo để vào lệnh...*")
                        
                with col_phai:
                    st.subheader("📝 Lịch Sử Giao Dịch")
                    if tong_lenh > 0:
                        st.dataframe(pd.DataFrame(lich_su).iloc[::-1], use_container_width=True, hide_index=True)
                    else:
                        st.write("Chưa có lệnh nào được chốt.")
