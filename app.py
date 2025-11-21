import streamlit as st
import pdfplumber
import pandas as pd
import re

st.title("WIO Bank PDF to CSV Converter")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    data = []
    valid_currencies = ["AED", "USD", "EUR", "GBP"]
    current_currency = None  # carry forward currency

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split("\n")

            # -------------------------------------------
            # UPDATED CURRENCY DETECTION (MOST ROBUST)
            # -------------------------------------------
            for line in lines:

                # Pattern 1: Balance (AED)
                bal_match = re.search(r"Balance\s*\((AED|USD|EUR|GBP)\)", line, re.IGNORECASE)
                if bal_match:
                    cur = bal_match.group(1).upper()
                    if cur in valid_currencies:
                        current_currency = cur
                        continue

                # Pattern 2: CURRENCY AED
                cur_match = re.search(r"CURRENCY\s*([A-Z]{3})", line)
                if cur_match:
                    cur = cur_match.group(1)
                    if cur in valid_currencies:
                        current_currency = cur
                        continue

                # Pattern 3: AED account
                acc_match = re.match(r"^([A-Z]{3})\s+account$", line.strip(), re.IGNORECASE)
                if acc_match:
                    cur = acc_match.group(1).upper()
                    if cur in valid_currencies:
                        current_currency = cur
                        continue

            # -------------------------------------------
            # STEP 2: EXTRACT TRANSACTIONS (same as yours)
            # -------------------------------------------
            for line in lines:

                # Date detection
                date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                if date_match:

                    date = date_match.group(1)
                    rest = date_match.group(2).split()

                    # Extract amount + balance
                    numbers = [p.replace(",", "") for p in rest if re.match(r"-?\d+(\.\d+)?$", p)]
                    if len(numbers) >= 2:
                        amount = float(numbers[-2])
                        balance = float(numbers[-1])

                        # Reference number = first token
                        reference = rest[0]

                        # Description = all tokens except ref + amount + balance
                        description = " ".join(rest[1:-2])

                        data.append([
                            date,
                            reference,
                            description,
                            amount,
                            balance,
                            current_currency  # use last detected currency
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
