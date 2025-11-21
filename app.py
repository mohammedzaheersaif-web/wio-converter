import streamlit as st
import pdfplumber
import pandas as pd
import re

st.title("WIO Bank PDF to CSV Converter")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    data = []
    current_currency = None

    valid_currencies = ["AED", "USD", "EUR", "GBP"]

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split("\n")

            for i, line in enumerate(lines):

                # -------------------------
                # FIXED CURRENCY DETECTION
                # -------------------------

                # Case 1: "CURRENCY" on a line alone, currency on next line
                if line.strip() == "CURRENCY":
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line in valid_currencies:
                            current_currency = next_line
                    continue

                # Case 2: "CURRENCY AED" in one line
                if "CURRENCY" in line:
                    parts = line.split()
                    for pt in parts:
                        if pt in valid_currencies:
                            current_currency = pt
                    continue

                # ---------------------------------
                # Detect transaction lines by date
                # ---------------------------------

                date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                if date_match:
                    date = date_match.group(1)
                    remaining = date_match.group(2).split()

                    # Extract numeric values (amount, balance)
                    numbers = [p.replace(",", "") for p in remaining if re.match(r"-?\d+(\.\d+)?", p)]

                    if len(numbers) >= 2:
                        amount = float(numbers[-2])
                        balance = float(numbers[-1])

                        # Clean proper debit/credit detection
                        # WIO negative values already show with "-" sign
                        # If no sign, assume positive
                        # We do NOT invert positive values.
                        # If amount is negative, keep it negative.
                        # If amount is positive, keep it positive.
                        
                        description = " ".join(remaining[:-2])

                        data.append([
                            date,
                            description,
                            amount,
                            balance,
                            current_currency
                        ])

    df = pd.DataFrame(data, columns=["Date", "Description", "Amount", "Balance", "Currency"])

    st.write("### Extracted Transactions")
    st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download CSV",
        data=csv,
        file_name="wio_transactions.csv",
        mime="text/csv",
    )
