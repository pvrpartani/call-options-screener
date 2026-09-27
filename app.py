import streamlit as st
import yfinance as yf
import pandas as pd
import requests

st.set_page_config(page_title="S&P 500 Options Calculator", layout="wide")
st.title("📈 Advanced S&P 500 Call Options Calculator")
st.write("Filter by specific or all expirations, credit received, premium yields, and strike prices.")

# --- Stealth Session for Yahoo Finance ---
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
})

@st.cache_data(ttl=86400)
def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(url, headers=headers)
    df = pd.read_html(response.text)[0]
    return df['Symbol'].str.replace('.', '-', regex=False).tolist()

tickers_list = get_sp500_tickers()

st.sidebar.header("1. Select Stocks")
selected_tickers = st.sidebar.multiselect("Choose S&P 500 Stocks:", tickers_list, default=["AAPL"])

if not selected_tickers:
    st.warning("Please select at least one stock.")
    st.stop()

@st.cache_data(ttl=3600)
def get_common_expirations(tickers):
    all_exps = set()
    for t in tickers:
        tkr = yf.Ticker(t, session=session)
        all_exps.update(tkr.options)
    return sorted(list(all_exps))

with st.spinner("Fetching available expiration dates..."):
    exp_dates = get_common_expirations(selected_tickers)

if not exp_dates:
    st.error("No options data available for the selected stocks.")
    st.stop()

st.sidebar.header("2. Expiration Dates")
load_all_exp = st.sidebar.checkbox("Load ALL Expirations (Can be slow)")
if load_all_exp:
    selected_exps = exp_dates
else:
    selected_exps = st.sidebar.multiselect("Select Expirations to Load:", exp_dates, default=exp_dates[:1])

if not selected_exps:
    st.warning("Please select at least one expiration date.")
    st.stop()

st.sidebar.header("3. Advanced Filters")
min_credit = st.sidebar.number_input("Min Credit ($ Premium)", min_value=0.0, value=0.50, step=0.1)
min_yield_pct = st.sidebar.number_input("Min Premium Yield (%)", min_value=0.0, value=1.0, step=0.1)
min_strike_ratio = st.sidebar.number_input("Min Strike vs Stock Price (%)", value=100.0, step=1.0)

@st.cache_data(ttl=900)
def load_options_data(tickers, exp_dates_list):
    calls_list = []
    for t in tickers:
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
                    
    return pd.concat(calls_list, ignore_index=True) if calls_list else pd.DataFrame()

with st.spinner(f"Loading options chains for {len(selected_exps)} dates..."):
    df_calls = load_options_data(selected_tickers, selected_exps)

if df_calls.empty:
    st.warning("No call options found for the selected criteria.")
    st.stop()

df_calls['Credit Received ($)'] = df_calls['bid'] * 100
df_calls['Premium Yield (%)'] = (df_calls['bid'] / df_calls['Underlying_Price']) * 100
df_calls['Strike/Stock Ratio (%)'] = (df_calls['strike'] / df_calls['Underlying_Price']) * 100
df_calls['Covered_Call_Breakeven'] = df_calls['Underlying_Price'] - df_calls['bid']

filtered_df = df_calls[
    (df_calls['bid'] >= min_credit) & 
    (df_calls['Premium Yield (%)'] >= min_yield_pct) &
    (df_calls['Strike/Stock Ratio (%)'] >= min_strike_ratio)
].copy()

filtered_df = filtered_df.sort_values(by=['Expiration', 'Ticker', 'strike'])

cols_to_display = [
    'Expiration', 'Ticker', 'Underlying_Price', 'strike', 'bid', 
    'impliedVolatility', 'Credit Received ($)', 'Premium Yield (%)', 
    'Strike/Stock Ratio (%)', 'Covered_Call_Breakeven'
]

st.subheader(f"Filtered Results: Found {len(filtered_df)} Contracts")
if filtered_df.empty:
    st.info("No contracts matched your filters. Try adjusting them in the sidebar.")
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
