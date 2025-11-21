import streamlit as st
from pdfminer.high_level import extract_text
import pandas as pd
import re

st.title("WIO Bank PDF to CSV Converter")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:

    # Extract all text using pdfminer (works correctly for WIO)
    text = extract_text(uploaded_file)

    # Split into clean lines
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    data = []
    valid_currencies = ["AED", "GBP", "USD", "EUR"]
    current_currency = None

    # ---------------------------------------------------------
    # STEP 1 — Detect currency for each block of transactions
    # ---------------------------------------------------------
    for i, line in enumerate(lines):

        # Format 1: CURRENCY <CODE>
        m = re.search(r"CURRENCY\s*([A-Z]{3})", line)
        if m:
            code = m.group(1).upper()
            if code in valid_currencies:
                current_currency = code
            continue

        # Format 2: CURRENCY \n CODE
        if line == "CURRENCY" and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line in valid_currencies:
                current_currency = next_line
            continue

        # Format 3: <CODE> account
        m2 = re.match(r"^([A-Z]{3}) account$", line)
        if m2:
            code = m2.group(1).upper()
            if code in valid_currencies:
                current_currency = code
            continue

    # Safety fallback
    if current_currency is None:
        current_currency = "AED"

    # ---------------------------------------------------------
    # STEP 2 — Extract all transactions
    # ---------------------------------------------------------
    for line in lines:

        # Detect transactions (must begin with date)
        match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
        if not match:
            continue

        date = match.group(1)
        body = match.group(2).split()

        # Extract numeric values
        nums = [x.replace(",", "") for x in body if re.match(r"-?\d+(\.\d+)?$", x)]
        if len(nums) < 2:
            continue

        amount = float(nums[-2])
        balance = float(nums[-1])

        reference = body[0]
        description = " ".join(body[1:-2])

        data.append([
            date,
            reference,
            description,
            amount,
            balance,
            current_currency
        ])

    # Create DataFrame
    df = pd.DataFrame(data, columns=[
        "Date", "Reference", "Description",
        "Amount", "Balance", "Currency"
    ])

    st.write("### Extracted Transactions")
    st.dataframe(df)

    st.download_button(
        "Download CSV",
        df.to_csv(index=False).encode("utf-8"),
        "wio_transactions.csv",
        "text/csv"
    )
