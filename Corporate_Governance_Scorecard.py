import streamlit as st
import yfinance as yf
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from bs4 import BeautifulSoup
from googletrans import Translator
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

translator = Translator()
FINNHUB_API_KEY = "cuhju4hr01qva71u1mogcuhju4hr01qva71u1mp0"

# === Fetch ESG Data from Finnhub ===
def fetch_esg_data_finnhub(ticker):
    url = f"https://finnhub.io/api/v1/stock/esg?symbol={ticker}&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        return {
            "Environment Score": data.get("environmentScore", "N/A"),
            "Social Score": data.get("socialScore", "N/A"),
            "Governance Score": data.get("governanceScore", "N/A")
        }
    except Exception as e:
        st.error(f"Error fetching ESG data: {e}")
        return {}

# === Fetch Governance Data from Yahoo Finance ===
def fetch_yahoo_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        governance_data = stock.info

        officers = governance_data.get("companyOfficers", [])
        board_members = [officer.get("name", "N/A") for officer in officers if officer.get("title")]
        ceo = officers[0].get("name", "N/A") if officers else "N/A"
        chairman = next((officer.get("name", "N/A") for officer in officers if "Chairman" in officer.get("title", "")),
                        "N/A")
        esg_score = governance_data.get("esgScores", {}).get("totalEsg", "N/A")

        return {
            "CEO": ceo,
            "Chairman": chairman,
            "Board Members": board_members,
            "ESG Score": esg_score
        }
    except Exception as e:
        st.error(f"Error fetching Yahoo Finance data: {e}")
        return {}


# === Fetch Chinese & Taiwanese Governance Reports ===
def fetch_china_taiwan_reports(ticker):
    sina_url = f"https://finance.sina.com.cn/stock/governance/{ticker}.shtml"

    session = requests.Session()
    retry = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)

    reports = {}

    # Fetch Sina Finance Report
    try:
        response = session.get(sina_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        governance_texts = soup.find_all("p")[:3]
        reports["Sina Finance Report"] = " ".join([p.text for p in governance_texts])
    except Exception as e:
        reports["Sina Finance Report"] = f"Error fetching Sina report: {e}"

    # Skip China SEC Report if it fails
    try:
        china_sec_url = "https://www.csrc.gov.cn/pub/newsite/flb/flfg/"
        response_sec = session.get(china_sec_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup_sec = BeautifulSoup(response_sec.text, "html.parser")
        reports["China SEC Report"] = soup_sec.find("div", {"class": "content"}).text[:500]
    except Exception:
        reports["China SEC Report"] = "Could not fetch China SEC report due to SSL error."

    return reports


# === Translate Chinese Reports ===
def translate_text(text):
    try:
        return translator.translate(text, src="zh-cn", dest="en").text
    except Exception as e:
        return f"Translation Error: {e}"


# === Compute Corporate Governance Score ===
def compute_governance_score(yahoo_data):
    score = 0
    if yahoo_data.get("CEO") != "N/A":
        score += 20  # CEO data available
    if len(yahoo_data.get("Board Members", [])) >= 5:
        score += 30  # Strong board
    if yahoo_data.get("CEO") != yahoo_data.get("Chairman"):
        score += 50  # CEO-Chairman separation
    return min(score, 100)


# === Streamlit UI ===
st.title("Corporate Governance Scorecard Dashboard")

market = st.sidebar.selectbox("Select Market", ["USA (SEC)", "China (A-Shares)", "Taiwan (TSEC)"])
ticker = st.sidebar.text_input("Enter Stock Ticker", "MSFT")

if st.sidebar.button("Fetch Governance Data"):
    yahoo_data = fetch_yahoo_data(ticker)
    esg_data = fetch_esg_data_finnhub(ticker)
    sec_data = fetch_china_taiwan_reports(ticker) if market in ["China (A-Shares)", "Taiwan (TSEC)"] else {}
    governance_score = compute_governance_score(yahoo_data)

    if market in ["China (A-Shares)", "Taiwan (TSEC)"]:
        sec_data = {key: translate_text(value) for key, value in sec_data.items()}

    st.subheader(f"Corporate Governance Score: {governance_score}/100")
    st.write(f"**CEO:** {yahoo_data.get('CEO', 'N/A')}")
    st.write(f"**Chairman:** {yahoo_data.get('Chairman', 'N/A')}")
    st.write(
        f"**Board Members:** {', '.join(yahoo_data.get('Board Members', []) if yahoo_data.get('Board Members') else ['N/A'])}")

    # ESG Score Gauge Chart
    governance_score_value = esg_data.get("Governance Score", 0)
    if isinstance(governance_score_value, str) and not governance_score_value.replace('.', '', 1).isdigit():
        governance_score_value = 0  # Replace non-numeric values with 0

    fig_esg = go.Figure(go.Indicator(
        mode="gauge+number",
        value=float(governance_score_value),
        title={'text': "Governance Score"},
        gauge={'axis': {'range': [0, 100]}}
    ))
    st.plotly_chart(fig_esg)

    st.write("### Governance Reports")
    for key, value in sec_data.items():
        st.write(f"**{key}:** {value}")
    else:
        st.write("No governance reports available for the selected market.")

    # === Visualizations ===
    st.write("## Data Visualizations")

    # Check if board_members exists
    board_members = yahoo_data.get("Board Members", [])
    if board_members:
        # Board Independence Pie Chart
        df_independence = pd.DataFrame({"Category": ["Independent", "Non-Independent"],
                                        "Count": [len(board_members) // 2, len(board_members) // 2]})
        fig_pie = px.pie(df_independence, values="Count", names="Category", title="Board Independence")
        st.plotly_chart(fig_pie)

        # Board Gender Diversity (example: placeholder data)
        board_gender_count = {"Male": 3, "Female": 2}  # You should adjust this with actual data
        df_diversity = pd.DataFrame(
            {"Gender": ["Male", "Female"], "Count": [board_gender_count["Male"], board_gender_count["Female"]]})
        fig_diversity = px.pie(df_diversity, values="Count", names="Gender", title="Board Gender Diversity")
        st.plotly_chart(fig_diversity)