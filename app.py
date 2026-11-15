import streamlit as st
import yfinance as yf
import pandas as pd
import datetime

st.set_page_config(page_title="Bot Phân Tích XAU/USD", layout="centered")

def lay_du_lieu_vang_h1():
    df = yf.download("GC=F", period="15d", interval="1h", progress=False)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    return df

def phan_tich_ky_thuat(df):
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI_14'] = 100 - (100 / (1 + rs))
    
    ema_12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD_12_26_9'] = ema_12 - ema_26
    df['MACDs_12_26_9'] = df['MACD_12_26_9'].ewm(span=9, adjust=False).mean()
    
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['ATR_14'] = true_range.rolling(14).mean()
    
    df = df.dropna()
    return df.iloc[-1]

st.title("🥇 Bot Phân Tích Tín Hiệu Vàng (Khung H1)")
st.write(f"Cập nhật lúc: **{datetime.datetime.now().strftime('%H:%M:%S - %d/%m/%Y')}**")

if st.button("🔄 Quét Dữ Liệu Thị Trường", type="primary"):
    with st.spinner("Đang lấy dữ liệu từ Yahoo Finance..."):
        df_vang = lay_du_lieu_vang_h1()
        
        if df_vang is None:
            st.error("❌ Không thể lấy dữ liệu. Vui lòng thử lại sau.")
        else:
            nen_ht = phan_tich_ky_thuat(df_vang)
            gia_ht = float(nen_ht['Close'])
            ema_20 = float(nen_ht['EMA_20'])
            sma_50 = float(nen_ht['SMA_50'])
            rsi = float(nen_ht['RSI_14'])
            macd_line = float(nen_ht['MACD_12_26_9'])
            macd_signal = float(nen_ht['MACDs_12_26_9'])
            atr = float(nen_ht['ATR_14'])

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Giá Hiện Tại", f"{gia_ht:.2f}")
            c2.metric("EMA 20", f"{ema_20:.2f}")
            c3.metric("RSI (14)", f"{rsi:.1f}")
            c4.metric("Độ Biến Động (ATR)", f"{atr:.2f}")
            
            st.markdown("---")
            
            diem = 0
            
            st.subheader("🔎 Phân Tích Cấu Trúc")
            if gia_ht > ema_20:
                st.success("✅ Giá nằm TRÊN EMA 20 (+1)")
                diem += 1
            else:
                st.error("🔻 Giá nằm DƯỚI EMA 20 (-1)")
                diem -= 1
                
            if ema_20 > sma_50:
                st.success("✅ EMA 20 cắt LÊN SMA 50 (+1)")
                diem += 1
            else:
                st.error("🔻 EMA 20 cắt XUỐNG SMA 50 (-1)")
                diem -= 1
                
            if rsi > 50:
                st.success(f"✅ RSI = {rsi:.1f} (Lớn hơn 50) (+1)")
                diem += 1
            else:
                st.error(f"🔻 RSI = {rsi:.1f} (Nhỏ hơn 50) (-1)")
                diem -= 1

            if macd_line > macd_signal:
                st.success("✅ MACD ủng hộ xu hướng TĂNG (+1)")
                diem += 1
            else:
                st.error("🔻 MACD ủng hộ xu hướng GIẢM (-1)")
                diem -= 1

            st.markdown("---")
            st.subheader("🎯 Chiến Lược Khuyến Nghị")
            
            sl = atr * 1.5
            tp = atr * 3.0

            if diem >= 3:
                st.success("🔥 **XU HƯỚNG CHÍNH: TĂNG MẠNH (UPTREND)**")
                st.markdown(f"🟢 **LỆNH: BUY (LONG)** \n* **Entry:** Quanh {ema_20:.2f} \n* **Take Profit:** {gia_ht + tp:.2f} \n* **Stop Loss:** {gia_ht - sl:.2f}")
            elif diem <= -3:
                st.error("📉 **XU HƯỚNG CHÍNH: GIẢM MẠNH (DOWNTREND)**")
                st.markdown(f"🔴 **LỆNH: SELL (SHORT)** \n* **Entry:** Quanh {ema_20:.2f} \n* **Take Profit:** {gia_ht - tp:.2f} \n* **Stop Loss:** {gia_ht + sl:.2f}")
            else:
                st.warning("⚖️ **XU HƯỚNG CHÍNH: ĐI NGANG (SIDEWAYS)**")
                st.markdown("⚪ **LỆNH: ĐỨNG NGOÀI** \n* Các chỉ báo đang mâu thuẫn, chưa có điểm vào an toàn.")