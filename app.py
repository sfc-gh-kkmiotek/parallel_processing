import streamlit as st
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import plotly.express as px
import time

# Configure the page
st.set_page_config(page_title="Parallel API Dashboard", layout="wide")
st.title("📊 Real-time Parallel API Dashboard")

# Define API endpoints with simulated latencies
APIS = [
    {
        "name": "Weather API",
        "url": "https://api.open-meteo.com/v1/forecast",
        "params": {
            "latitude": 40.71,
            "longitude": -74.01,
            "hourly": "temperature_2m",
            "forecast_days": 1
        },
        "processor": "weather",
        "latency": 5.0  # Simulated latency in seconds
    },
    {
        "name": "Crypto Prices",
        "url": "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
        "params": {
            "vs_currency": "usd",
            "days": 7,
            "interval": "daily"
        },
        "processor": "crypto",
        "latency": 5.0
    },
    {
        "name": "Stock Market",
        "url": "https://www.alphavantage.co/query",
        "params": {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": "IBM",
            "interval": "5min",
            "apikey": "demo"
        },
        "processor": "stocks",
        "latency": 5.0
    }
]

@st.cache_data(ttl=60, show_spinner=False)
def fetch_api_data(api):
    try:
        response = requests.get(api["url"], params=api["params"])
        response.raise_for_status()
        return {
            "api": api,
            "data": response.json(),
            "error": None
        }
    except Exception as e:
        return {
            "api": api,
            "data": None,
            "error": str(e)
        }

def fetch_with_latency(api):
    """Wrapper function to add simulated latency"""
    start_time = time.time()
    result = fetch_api_data(api)

    # Simulate API latency
    time.sleep(api["latency"])

    # Calculate total API time including simulated latency
    result["api_time"] = time.time() - start_time
    return result

def process_data(result):
    start_time = time.time()
    if result["error"]:
        return None, result["error"], 0

    try:
        processor = result["api"]["processor"]
        data = result["data"]

        if processor == "weather":
            df = pd.DataFrame({
                "time": data["hourly"]["time"],
                "temperature": data["hourly"]["temperature_2m"]
            })
            fig = px.line(df, x="time", y="temperature",
                          title="Hourly Temperature Forecast")

        elif processor == "crypto":
            df = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
            df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
            fig = px.area(df, x="date", y="price",
                          title="Bitcoin Price (7 Days)")

        elif processor == "stocks":
            ts = data.get("Time Series (5min)", {})
            df = pd.DataFrame([
                {"time": k, "price": float(v["1. open"])}
                for k, v in ts.items()
            ])
            fig = px.line(df, x="time", y="price",
                          title="IBM Stock Price (5min intervals)")

        return fig, None, time.time() - start_time

    except Exception as e:
        return None, str(e), time.time() - start_time

def main():
    # Create layout columns and placeholders
    cols = st.columns(len(APIS))
    placeholders = [col.empty() for col in cols]
    status_bars = [col.empty() for col in cols]

    # Initialize status indicators
    for idx, bar in enumerate(status_bars):
        with bar:
            st.subheader(APIS[idx]["name"])
            st.caption("⌛ Initializing...")

    # Fetch and process data with parallel execution
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(fetch_with_latency, api): idx
                   for idx, api in enumerate(APIS)}

        for future in as_completed(futures):
            idx = futures[future]
            result = future.result()
            status_bars[idx].empty()

            with placeholders[idx]:
                col = cols[idx]
                with col:
                    st.subheader(result["api"]["name"])

                    if result["error"]:
                        st.error(f"API Error: {result['error']}")
                        st.metric("API Time", f"{result['api_time']:.2f}s")
                        continue

                    # Process data with timing
                    fig, error, processing_time = process_data(result)

                    if error:
                        st.error(f"Processing Error: {error}")
                    else:
                        st.plotly_chart(fig, use_container_width=True)

                    # Display timing metrics
                    st.metric("API Time (incl. latency)",
                              f"{result['api_time']:.2f}s")
                    st.metric("Processing Time",
                              f"{processing_time:.2f}s")

if __name__ == "__main__":
    main()
