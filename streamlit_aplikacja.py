# pip install yfinance plotly streamlit-autorefresh

import sqlite3
from datetime import datetime
import pandas as pd
import yfinance as yf
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

# ————————————————————————————————————————————————
# 0. GLOBALNY CSS: jasne tło, czarne elementy, subtelne odcienie
# ————————————————————————————————————————————————
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
    background-color: #EFEFEF !important;
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
    color: #fff;
    font-size: 14px !important;
}

/* Kontener aplikacji */
.block-container {
    padding: 1rem 1rem 2rem 1rem !important;
    max-width: 100% !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #000 !important;
    width: 150px !important;
    flex: 0 0 150px !important;
    padding-top: 0.5rem !important;
    border-radius: 0 15px 15px 0;
}

/* Główna sekcja zaokrąglona */
[data-testid="stVerticalBlock"] > div {
    background: #FFFFFF;
    padding: 1rem;
    border-radius: 15px;
    margin-top: 0.5rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

/* Nagłówki i metryki */
h1, h2, h3, .stMetric-label, .stMetric-value {
    color: #000000 !important;
    font-size: 0.9em !important;
}

/* Przycisk */
div.stButton > button {
    background-color: #000 !important;
    color: #FFF !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
    border: none;
    font-size: 0.8em !important;
    padding: 0.25em 0.5em !important;
    height: auto !important;
}
div.stButton > button:hover {
    background-color: #333 !important;
}

/* Inputy */
input, .stNumberInput input, .stTextInput input {
    background-color: #FFF !important;
    color: #000 !important;
    border: 1px solid #CCC !important;
    border-radius: 6px !important;
    padding: 0.25em 0.5em !important;
    font-size: 0.8em !important;
    height: auto !important;
}

/* Expander */
.streamlit-expanderHeader {
    background-color: #DDD !important;
    color: #000 !important;
    border-radius: 6px !important;
    font-size: 0.9em !important;
    padding: 0.5em 1em !important;
}

/* Alerty */
div.stAlert [role="alert"] {
    border-radius: 6px !important;
    padding: 0.5em 0.75em !important;
    font-size: 0.8em !important;
}

/* Ukryj dekoracje */
[data-testid="stDecoration"] { display: none !important; }

/* Tabele */
.dataframe {
    font-size: 0.8em !important;
}

/* Kolumny */
.st-cb { padding: 0.25rem !important; }
</style>
""", unsafe_allow_html=True)

# —————————————————————————————
# 1. AUTO-ODŚWIEŻANIE co 30 s
# —————————————————————————————
st_autorefresh(interval=30_000, limit=None, key="data_refresh")

# —————————————————————————————
# 2. POŁĄCZENIE Z BAZĄ
# —————————————————————————————
conn = sqlite3.connect("portfolio.db", check_same_thread=False)
c = conn.cursor()

# —————————————————————————————
# 3. SIDEBAR: pusty expander na przyszłe menu
# —————————————————————————————
with st.sidebar.expander("📂 Menu", expanded=True):
    st.write("…")

# —————————————————————————————
# 4. SEKCJA GÓRNA: SALDO + WYKRES
# —————————————————————————————
hist = pd.read_sql("SELECT * FROM balance_history ORDER BY date DESC", conn)
hist["date"] = pd.to_datetime(hist["date"])
balance = hist.iloc[0]["balance"] if not hist.empty else 0
prev_balance = hist.iloc[1]["balance"] if len(hist) > 1 else balance
change_usd = balance - prev_balance
change_pct = (change_usd / prev_balance * 100) if prev_balance else 0

# Układ 3 kolumn obok siebie
col1, col2, col3 = st.columns([2, 3, 5])

with col1:
    st.metric("Saldo", f"{balance:.2f} USD", f"{change_pct:+.2f}%")

with col2:
    add_amt = st.number_input("Dodaj środki", min_value=0.0, step=100.0, format="%.2f", label_visibility="collapsed")
    if st.button("💸 Dodaj", use_container_width=True):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_balance = balance + add_amt
        c.execute("INSERT INTO balance_history(date,balance) VALUES(?,?)", (now, new_balance))
        conn.commit()
        st.success(f"Dodano {add_amt:.2f} USD")

with col3:
    if not hist.empty:
        fig = go.Figure(go.Scatter(
            x=hist["date"], y=hist["balance"],
            line=dict(color="green", width=2)
        ))
        fig.update_layout(
            height=80,
            margin=dict(t=5, b=5, l=0, r=0),
            xaxis=dict(showgrid=False, title=None),
            yaxis=dict(showgrid=False, title=None),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
        )
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# —————————————————————————————
# 5. SEKCJA GŁÓWNA: 2 KOLUMNY
# —————————————————————————————
left_col, right_col = st.columns([4, 6])

with left_col:
    # —————————————————————————————
    # 5.1 LEWA KOLUMNA: GÓRNA CZĘŚĆ (2 KOLUMNY)
    # —————————————————————————————
    col_left1, col_left2 = st.columns(2)
    
    with col_left1:
        # Wykres donutowy
        df = pd.read_sql("SELECT * FROM portfolio", conn)
        if not df.empty:
            st.markdown("**Dystrybucja kapitału**")
            dist = df.groupby("instrument")["own_capital"].sum().reset_index()
            fig_donut = go.Figure(px.pie(dist, values="own_capital", names="instrument", hole=0.5))
            fig_donut.update_traces(marker=dict(colors=px.colors.sequential.Emrld))
            fig_donut.update_layout(
                margin=dict(t=0,b=0,l=0,r=0),
                paper_bgcolor='rgba(0,0,0,0)', 
                plot_bgcolor='rgba(0,0,0,0)',
                height=200,
                showlegend=False
            )
            st.plotly_chart(fig_donut, use_container_width=True)
    
    with col_left2:
        # Formularz dodawania pozycji
        with st.expander("➕ Dodaj pozycję", expanded=False):
            with st.form("add_form", clear_on_submit=True):
                inst = st.text_input("Symbol")
                pr = st.number_input("Cena wejścia", min_value=0.0, format="%.2f", step=0.01)
                qty = st.number_input("Ilość", min_value=0.01, format="%.2f", step=0.01)
                lev = st.number_input("Dźwignia", min_value=1.0, format="%.2f", step=0.1)
                own = st.number_input("Kapitał", min_value=0.01, format="%.2f", step=0.01)
                swp = st.number_input("Swap", min_value=0.0, format="%.2f", step=0.01)
                submit = st.form_submit_button("Zapisz")
                if submit:
                    if not all([inst, pr>0, qty>0, lev>0, own>0, swp>=0]):
                        st.error("Uzupełnij poprawnie wszystkie pola.")
                    elif yf.Ticker(inst.upper()).history(period="1d", interval="1m").empty:
                        st.error("Nie znaleziono symbolu.")
                    else:
                        c.execute("""
                            INSERT INTO portfolio
                            (instrument,entry_price,quantity,leverage,own_capital,swap)
                            VALUES(?,?,?,?,?,?)
                        """, (inst.upper(), pr, qty, lev, own, swp))
                        conn.commit()
                        st