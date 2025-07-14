import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from fuzzywuzzy import process

# Load company list (name + screener slug)
@st.cache_data
def load_company_list():
    df = pd.read_csv("company_list.csv")
    return df

# Fetch data from Screener.in
def fetch_screener_data(slug):
    url = f"https://www.screener.in/company/{slug}/consolidated/"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    # Try to find Market Cap, EPS, and Free Cash Flow
    data = {}
    try:
        facts = soup.find_all("li", class_="flex flex-space-between")
        for fact in facts:
            label = fact.find("span").text.strip()
            value = fact.find_all("span")[-1].text.strip()
            data[label] = value
    except:
        pass

    try:
        fcf_table = soup.find("section", id="cash-flow").find("table")
        fcf_row = fcf_table.find_all("tr")[1]
        fcf_values = [td.text.replace(",", "") for td in fcf_row.find_all("td")[1:]]
        fcf_values = list(map(float, fcf_values[-5:]))
        data["FCF_5Y"] = fcf_values
    except:
        data["FCF_5Y"] = []

    return data

# Reverse DCF Calculation
def reverse_dcf(fcf_or_eps, discount_rate, terminal_rate, years, mode):
    values = fcf_or_eps
    if len(values) < years:
        st.error("Not enough data for the selected forecast period.")
        return None

    values = values[-years:]
    present_value = 0
    for i in range(years):
        present_value += values[i] / ((1 + discount_rate) ** (i + 1))

    terminal_value = values[-1] * (1 + terminal_rate) / (discount_rate - terminal_rate)
    terminal_value /= ((1 + discount_rate) ** years)
    intrinsic_value = present_value + terminal_value
    return intrinsic_value

# Main app
def main():
    st.title("📊 Reverse DCF Valuation Tool")

    df_companies = load_company_list()
    company_names = df_companies["name"].tolist()
    user_input = st.text_input("Enter company name:")
    match, score = process.extractOne(user_input, company_names) if user_input else ("", 0)

    if score > 70:
        slug = df_companies[df_companies["name"] == match]["slug"].values[0]
        st.success(f"Selected Company: {match}")

        data = fetch_screener_data(slug)
        st.write("📑 Fetched Data:", data)

        mode = st.radio("Valuation Mode", ["FCF-based", "Earnings-based"])

        discount_rate = st.slider("Discount Rate (%)", 5, 15, 10) / 100
        terminal_rate = st.slider("Terminal Growth Rate (%)", 1, 6, 3) / 100
        years = st.slider("Forecast Years", 3, 10, 5)

        if mode == "FCF-based":
            if "FCF_5Y" in data and len(data["FCF_5Y"]) > 0:
                intrinsic_value = reverse_dcf(data["FCF_5Y"], discount_rate, terminal_rate, years, mode)
                if intrinsic_value:
                    st.metric("📈 Intrinsic Value (FCF)", f"{intrinsic_value:.2f} Cr")
            else:
                st.warning("FCF data not available.")
        else:
            try:
                eps = float(data["EPS (TTM)"].replace("₹", "").strip())
                earnings = [eps * (1 + terminal_rate) ** i for i in range(years)]
                intrinsic_value = reverse_dcf(earnings, discount_rate, terminal_rate, years, mode)
                if intrinsic_value:
                    st.metric("📈 Intrinsic Value (Earnings)", f"{intrinsic_value:.2f} ₹/share")
            except:
                st.warning("EPS data not available or not numeric.")
    else:
        if user_input:
            st.warning("No close match found.")

if __name__ == "__main__":
    main()
