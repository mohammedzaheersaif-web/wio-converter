import streamlit as st
from pdfminer.high_level import extract_text
import pandas as pd
import re

st.title("WIO Bank PDF to CSV Converter")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    text = extract_text(uploaded_file)

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    data = []
    valid_currencies = ["AED", "USD", "GBP", "EUR"]
    current_currency = None

    # -----------------------------------------
    # FIXED: Reliable Currency Detection
    # -----------------------------------------
    for i, line in enumerate(lines):

        # Pattern 1: CURRENCY: AED
        m = re.search(r"CURRENCY[:\s]+([A-Z]{3})", line)
        if m:
            code = m.group(1)
            if code in valid_currencies:
                current_currency = code

        # Pattern 2: Next line style
        if line == "CURRENCY" and i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            if nxt in valid_currencies:
                current_currency = nxt

        # Pattern 3: USD account
        m = re.match(r"([A-Z]{3}) account", line, re.IGNORECASE)
        if m:
            code = m.group(1).upper()
            if code in valid_currencies:
                current_currency = code

    if current_currency is None:
        current_currency = "AED"

    # -----------------------------------------
    # Extract Transactions
    # -----------------------------------------
    for line in lines:
        m = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
        if not m:
            continue

        date = m.group(1)
        rest = m.group(2).split()

        nums = [p.replace(",", "") for p in rest if re.match(r"-?\d+(\.\d+)?", p)]
        if len(nums) < 2:
            continue

        amount = float(nums[-2])
        balance = float(nums[-1])

        reference = rest[0]
        description = " ".join(rest[1:-2])

        data.append([date, reference, description, amount, balance, current_currency])

    df = pd.DataFrame(data, columns=["Date", "Reference", "Description", "Amount", "Balance", "Currency"])

    st.dataframe(df)

    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"))
