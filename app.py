import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
from datetime import datetime, timedelta

st.set_page_config(page_title="Options Calculator", layout="wide")
st.title("📈 Call Options Calculator")
st.write("Filter call options by credit received, premium yield, and strike price.")

# --- Stealth Session for Yahoo Finance & Wikipedia ---
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
})

@st.cache_data(ttl=86400)
def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(url, headers=headers)
    df = pd.read_html(io.StringIO(response.text))[0]
    return df['Symbol'].str.replace('.', '-', regex=False).tolist()

high_vol_favorites = ["TSLA", "SPCX", "AMD", "NVDA", "COIN", "MSTR", "MARA", "RIOT", "PLTR", "UPST", "QQQ"]

# --- 1. STOCK SELECTION ---
st.subheader("1. Select Stocks")

selected_tickers = []

# S&P 500 Master Tickbox
scan_all_sp500 = st.checkbox("⚡ Scan ALL 500+ S&P 500 Tickers", value=False)

# Favorites Tickboxes
st.markdown("**🔥 High-Volatility Favorites**")
select_all_favs = st.checkbox("Select All Favorites", value=False)
cols = st.columns(3)
defaults = ["TSLA", "SPCX", "QQQ", "NVDA"]

for i, ticker in enumerate(high_vol_favorites):
    with cols[i % 3]:
        is_checked = True if select_all_favs else (ticker in defaults)
        if st.checkbox(ticker, value=is_checked, key=f"fav_{ticker}"):
            if ticker not in selected_tickers:
                selected_tickers.append(ticker)

tickers_list = get_sp500_tickers()

if scan_all_sp500:
    st.info(f"Loaded all {len(tickers_list)} S&P 500 tickers for scanning.")
    for t in tickers_list:
        if t not in selected_tickers:
            selected_tickers.append(t)
else:
    # Manual selection box only appears if "Scan ALL" is unticked
    manual_sp500 = st.multiselect("Or Search Specific S&P 500 Stocks:", tickers_list, default=[])
    for t in manual_sp500:
        if t not in selected_tickers:
            selected_tickers.append(t)

if not selected_tickers:
    st.warning("Please tick or select at least one stock to scan.")
    st.stop()

@st.cache_data(ttl=3600)
def get_common_expirations(tickers):
    all_exps = set()
    sample_tickers = tickers[:10] if len(tickers) > 20 else tickers
    for t in sample_tickers:
        tkr = yf.Ticker(t, session=session)
        all_exps.update(tkr.options)
    return sorted(list(all_exps))

with st.spinner("Fetching available expiration dates..."):
    exp_dates = get_common_expirations(selected_tickers)

if not exp_dates:
    st.error("No options data available for the selected stocks.")
    st.stop()

# --- 2. EXPIRATIONS ---
st.subheader("2. Expiration Dates")

st.caption("Auto-select expirations up to:")
auto_screen = st.radio(
    "Auto-Screen Window:", 
    ["4 Weeks", "5 Weeks", "6 Weeks", "7 Weeks", "8 Weeks", "Manual Selection"], 
    index=0, 
    horizontal=True,
    label_visibility="collapsed"
)

if auto_screen != "Manual Selection":
    weeks_out = int(auto_screen.split(" ")[0])
    target_date = datetime.now() + timedelta(weeks=weeks_out)
    selected_exps = [d for d in exp_dates if datetime.strptime(d, '%Y-%m-%d') <= target_date]
    st.success(f"Auto-selected {len(selected_exps)} expiration dates within the next {weeks_out} weeks.")
else:
    selected_exps = st.multiselect("Select Specific Expirations:", exp_dates, default=exp_dates[:1])

if not selected_exps:
    st.warning("Please select at least one expiration date.")
    st.stop()

# --- 3. FILTER PARAMETERS ---
st.subheader("3. Filter Parameters")
f_col1, f_col2, f_col3 = st.columns(3)
with f_col1:
    min_credit = st.number_input("Min Credit ($ Premium)", min_value=0.0, value=0.50, step=0.1)
with f_col2:
    min_yield_pct = st.number_input("Min Premium Yield (%)", min_value=0.0, value=1.0, step=0.1)
with f_col3:
    # Default set to 120.0
    min_strike_ratio = st.number_input("Min Strike vs Stock (%)", value=120.0, step=1.0)

@st.cache_data(ttl=900)
def load_options_data(tickers, exp_dates_list):
    calls_list = []
    progress_bar = st.progress(0) if len(tickers) > 20 else None
    
    for idx, t in enumerate(tickers):
        if progress_bar:
            progress_bar.progress((idx + 1) / len(tickers))
            
        tkr = yf.Ticker(t, session=session)
        try:
            current_price = tkr.history(period="1d")['Close'].iloc[-1]
        except:
            continue
            
        for exp in exp_dates_list:
            if exp in tkr.options:
                try:
                    chain = tkr.option_chain(exp).calls
                    chain['Ticker'] = t
                    chain['Expiration'] = exp
                    chain['Underlying_Price'] = current_price
                    calls_list.append(chain)
                except Exception:
                    pass
                    
    if progress_bar:
        progress_bar.empty()
        
    return pd.concat(calls_list, ignore_index=True) if calls_list else pd.DataFrame()

with st.spinner(f"Loading options chains for {len(selected_tickers)} ticker(s) across {len(selected_exps)} expiration date(s)..."):
    df_calls = load_options_data(selected_tickers, selected_exps)

if df_calls.empty:
    st.warning("No call options found for the selected criteria.")
    st.stop()

# Calculations
df_calls['Credit Received ($)'] = df_calls['bid'] * 100
df_calls['Premium Yield (%)'] = (df_calls['bid'] / df_calls['Underlying_Price']) * 100
df_calls['Strike/Stock Ratio (%)'] = (df_calls['strike'] / df_calls['Underlying_Price']) * 100
df_calls['Covered_Call_Breakeven'] = df_calls['Underlying_Price'] - df_calls['bid']

# Apply Filters
filtered_df = df_calls[
    (df_calls['bid'] >= min_credit) & 
    (df_calls['Premium Yield (%)'] >= min_yield_pct) &
    (df_calls['Strike/Stock Ratio (%)'] >= min_strike_ratio)
].copy()

# Sort by Premium Yield descending
filtered_df = filtered_df.sort_values(by=['Premium Yield (%)', 'Expiration'], ascending=[False, True])

cols_to_display = [
    'Expiration', 'Ticker', 'Underlying_Price', 'strike', 'bid', 
    'impliedVolatility', 'Credit Received ($)', 'Premium Yield (%)', 
    'Strike/Stock Ratio (%)', 'Covered_Call_Breakeven'
]

# --- 4. RESULTS TABLE ---
st.subheader(f"Filtered Results: Found {len(filtered_df)} Contracts")
if filtered_df.empty:
    st.info("No contracts matched your filters. Try adjusting them above.")
else:
    st.dataframe(filtered_df[cols_to_display].style.format({
        'Underlying_Price': '${:.2f}',
        'strike': '${:.2f}',
        'bid': '${:.2f}',
        'impliedVolatility': '{:.1%}',
        'Credit Received ($)': '${:.2f}',
        'Premium Yield (%)': '{:.2f}%',
        'Strike/Stock Ratio (%)': '{:.1f}%',
        'Covered_Call_Breakeven': '${:.2f}'
    }), use_container_width=True)
