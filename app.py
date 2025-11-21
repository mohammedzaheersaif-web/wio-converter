import streamlit as st
import pdfplumber
import pandas as pd
import re

st.title("WIO Bank PDF to CSV Converter")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    data = []
    valid_currencies = ["AED", "USD", "EUR", "GBP"]

    with pdfplumber.open(uploaded_file) as pdf:

        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = [l.strip() for l in text.split("\n") if l.strip()]

            # Extract currency from: Balance (AED)
            current_currency = None
            for line in lines:
                m = re.search(r"Balance\s*\((AED|USD|EUR|GBP)\)", line)
                if m:
                    current_currency = m.group(1)
                    break

            if not current_currency:
                continue  # Skip page if no currency identified

            # Extract transactions
            for line in lines:
                match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                if not match:
                    continue

                date = match.group(1)
                parts = match.group(2).split()

                numbers = [p.replace(",", "") for p in parts if re.match(r"-?\d+(\.\d+)?$", p)]
                if len(numbers) < 2:
                    continue

                amount = float(numbers[-2])
                balance = float(numbers[-1])
                reference = parts[0]
                description = " ".join(parts[1:-2])

                data.append([
                    date,
                    reference,
                    description,
                    amount,
                    balance,
                    current_currency
                ])

    df = pd.DataFrame(data, columns=[
        "Date", "Reference", "Description", "Amount", "Balance", "Currency"
    ])

    st.write("### Extracted Transactions")
    st.dataframe(df)

    st.download_button(
        "Download CSV",
        df.to_csv(index=False).encode("utf-8"),
        "wio_transactions.csv",
        "text/csv"
    )
