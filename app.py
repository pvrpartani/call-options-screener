# 11 High Volatility & Liquid Favorites
high_vol_favorites = ["TSLA", "SPCX", "AMD", "NVDA", "COIN", "MSTR", "MARA", "RIOT", "PLTR", "UPST", "QQQ"]

st.sidebar.header("1. Select Stocks")

# Checkbox to toggle between High Volatility Favorites and S&P 500
use_favorites = st.sidebar.checkbox("🔥 Use High-Volatility Favorites", value=True, help="Switch between curated high-premium stocks and the entire S&P 500.")

if use_favorites:
    # Set SPCX and QQQ to be selected automatically by default
    selected_tickers = st.sidebar.multiselect("Favorites:", high_vol_favorites, default=["TSLA", "SPCX", "QQQ", "NVDA"])
