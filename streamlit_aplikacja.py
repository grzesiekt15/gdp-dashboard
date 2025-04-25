# pip install yfinance --upgrade
# pip install plotly --upgrade
# pip install streamlit-autorefresh

import sqlite3
from datetime import datetime
import pandas as pd
import yfinance as yf
import streamlit as st
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# —————————————————————
# 1. AUTO-ODŚWIEŻANIE co 30 s
# —————————————————————
st_autorefresh(interval=30_000, limit=None, key="data_refresh")

# —————————————————————
# 2. POŁĄCZENIE I MIGRACJA BAZY
# —————————————————————
conn = sqlite3.connect("portfolio.db", check_same_thread=False)
c = conn.cursor()

# Główna tabela portfela
c.execute("""
CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument TEXT,
    entry_price REAL,
    quantity REAL,
    leverage REAL,
    own_capital REAL,
    swap REAL,
    date_added TEXT DEFAULT CURRENT_DATE
)
""")
# Historia salda
c.execute("""
CREATE TABLE IF NOT EXISTS balance_history (
    date TEXT,
    balance REAL
)
""")
conn.commit()

# —————————————————————
# 3. SALDO KONT A UKRYWANIE
# —————————————————————
# Pobranie ostatniego zapisanego salda
last = pd.read_sql("SELECT balance FROM balance_history ORDER BY date DESC LIMIT 1", conn)
if not last.empty:
    balance = last.iloc[0,0]
else:
    # jeśli nie ma historii, saldo = suma kapitału własnego
    tmp = pd.read_sql("SELECT SUM(own_capital) as s FROM portfolio", conn)
    balance = float(tmp['s'].iloc[0] or 0)

st.markdown("## 💰 Twoje saldo (USD)")
show = st.checkbox("Pokaż saldo", value=False)
if show:
    st.markdown(f"### **{balance:.2f} USD**")
else:
    # maskujemy gwiazdkami
    stars = "*" * len(f"{int(balance):d}")
    st.markdown(f"### **{stars}**")

# —————————————————————
# 4. DODAWANIE WIRTUALNYCH ŚRODKÓW
# —————————————————————
st.markdown("---")
st.subheader("Dodaj wirtualne środki")
add_amt = st.number_input("Kwota (USD)", min_value=0.0, step=100.0, format="%.2f")
if st.button("Dodaj środki"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_balance = balance + add_amt
    c.execute("INSERT INTO balance_history (date,balance) VALUES (?,?)", (now, new_balance))
    conn.commit()
    st.success(f"Dodano {add_amt:.2f} USD. Nowe saldo: {new_balance:.2f} USD")
    #st.experimental_rerun()

# —————————————————————
# 5. POBRANIE POSZCZEGOŁÓW I DYNAMICZNY PROFIT
# —————————————————————
@st.cache_data
def get_current_prices(tickers: list[str]) -> dict[str, float]:
    out = {}
    for t in tickers:
        try:
            hist = yf.Ticker(t).history(period="1d", interval="1m")
            out[t] = hist["Close"].iloc[-1] if not hist.empty else None
        except:
            out[t] = None
    return out

def calc_profit(entry, current, qty, lev):
    if current is None:
        return None
    return (current - entry) * qty * lev

df = pd.read_sql("SELECT * FROM portfolio", conn)
if not df.empty:
    prices = get_current_prices(df["instrument"].unique().tolist())
    df["current_price"] = df["instrument"].map(prices)
    df["profit"] = df.apply(
        lambda r: calc_profit(r["entry_price"], r["current_price"], r["quantity"], r["leverage"]),
        axis=1
    )
    st.subheader("Twoje pozycje z dynamicznym zyskiem")
    st.dataframe(df[[
        "instrument","entry_price","current_price",
        "quantity","leverage","own_capital","profit"
    ]], use_container_width=True)

    # dystrybucja kapitału
    st.subheader("Dystrybucja kapitału własnego")
    dist = df.groupby("instrument")["own_capital"].sum().reset_index()
    fig1 = px.bar(dist, x="instrument", y="own_capital",
                  labels={"own_capital":"Kapitał własny"},
                  title="Zainwestowano w instrumenty")
    st.plotly_chart(fig1, use_container_width=True)
else:
    st.info("Brak pozycji w portfelu. Dodaj pierwszą!")

# —————————————————————
# 6. WYKRES SALDA W CZASIE
# —————————————————————
hist = pd.read_sql("SELECT * FROM balance_history", conn)
if not hist.empty:
    hist["date"] = pd.to_datetime(hist["date"])
    st.subheader("Historia salda konta inwestycyjnego")
    fig2 = px.line(hist, x="date", y="balance",
                   labels={"balance":"Saldo USD","date":"Data"},
                   title="Saldo w czasie")
    st.plotly_chart(fig2, use_container_width=True)

# Wybór interwału dla salda
st.subheader("Historia salda konta inwestycyjnego")
interval = st.selectbox(
    "Pokaż saldo z ostatnich:",
    ["1h","12h","1d","1w","1m","6m","1y"],
    index=2
)

# Mapowanie na Timedelta
delta_map = {
    "1h": pd.Timedelta(hours=1),
    "12h": pd.Timedelta(hours=12),
    "1d": pd.Timedelta(days=1),
    "1w": pd.Timedelta(weeks=1),
    "1m": pd.Timedelta(days=30),
    "6m": pd.Timedelta(days=180),
    "1y": pd.Timedelta(days=365),
}

# Wczytanie pełnej historii
hist = pd.read_sql("SELECT * FROM balance_history", conn)
hist["date"] = pd.to_datetime(hist["date"])

# Filtrowanie wg interwału
now = pd.Timestamp.now()
cutoff = now - delta_map[interval]
hist_filt = hist[hist["date"] >= cutoff]

if not hist_filt.empty:
    fig2 = px.line(
        hist_filt,
        x="date",
        y="balance",
        labels={"balance":"Saldo USD","date":"Data"},
        title=f"Saldo w czasie (ostatnie {interval})"
    )
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info(f"Brak zapisów salda w ostatnim przedziale {interval}.")



# —————————————————————
# 7. DODAWANIE NOWYCH POZYCJI Z WALIDACJĄ
# —————————————————————
st.markdown("---")
st.subheader("Dodaj nową pozycję")

def symbol_exists(sym:str) -> bool:
    info = yf.Ticker(sym).history(period="1d", interval="1m")
    return not info.empty

with st.form("add_form", clear_on_submit=True):
    instrument = st.text_input("Symbol instrumentu").upper()
    entry_price = st.number_input("Cena wejścia", min_value=0.0, format="%.2f")
    quantity = st.number_input("Ilość", min_value=1.0, format="%.2f")
    leverage = st.number_input("Dźwignia", min_value=1.0, format="%.2f")
    own_capital = st.number_input("Kapitał własny", min_value=0.0, format="%.2f")
    swap = st.number_input("Swap", min_value=0.0, format="%.2f")
    submitted = st.form_submit_button("Dodaj pozycję")

    if submitted:
        # sprawdzamy puste pola
        if not all([instrument, entry_price, quantity, leverage, own_capital, swap is not None]):
            st.error("Proszę uzupełnić wszystkie pola.")
        # walidujemy symbol
        elif not symbol_exists(instrument):
            st.error("Nie znaleziono symbolu w Yahoo Finance.")
        else:
            # wszystko OK – zapisujemy
            c.execute("""
                INSERT INTO portfolio 
                (instrument, entry_price, quantity, leverage, own_capital, swap)
                VALUES (?,?,?,?,?,?)
            """, (instrument, entry_price, quantity, leverage, own_capital, swap))
            conn.commit()
            st.success(f"Dodano pozycję: {instrument}")
            #st.experimental_rerun()

# zamykamy połączenie
conn.close()
