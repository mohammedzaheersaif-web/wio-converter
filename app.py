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

            lines = text.split("\n")
            current_currency = None

            # -------------------------------------------------------
            # STEP 1: UNIVERSAL CURRENCY DETECTION (AED, GBP, USD)
            # -------------------------------------------------------

            for i, line in enumerate(lines):

                # Case 1: "CURRENCY GBP", "CURRENCY USD", etc.
                match = re.search(r"CURRENCY\s+([A-Z]{3})", line)
                if match:
                    current_currency = match.group(1)
                    continue

                # Case 2: "CURRENCY" then next line = AED/GBP/USD
                if line.strip() == "CURRENCY" and i + 1 < len(lines):
                    nxt = lines[i + 1].strip()
                    if nxt in valid_currencies:
                        current_currency = nxt
                    continue

                # Case 3: "USD account", "GBP account", "AED account"
                acc_match = re.match(r"^([A-Z]{3})\s+account$", line.strip())
                if acc_match:
                    current_currency = acc_match.group(1)
                    continue

            # If currency still not detected, fallback to last known or AED
            if current_currency is None:
                current_currency = "AED"

            # -------------------------------------------------------
            # STEP 2: EXTRACT TRANSACTIONS
            # -------------------------------------------------------

            for line in lines:

                # Detect date at start of line
                date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                if date_match:

                    date = date_match.group(1)
                    rest = date_match.group(2).split()

                    # Extract numeric values (amount, balance)
                    numbers = [p.replace(",", "") for p in rest if re.match(r"-?\d+(\.\d+)?", p)]

                    if len(numbers) >= 2:
                        amount = float(numbers[-2])
                        balance = float(numbers[-1])

                        # Extract reference number (always first column)
                        reference = rest[0]

                        # Description is all text between reference → amount
                        description = " ".join(rest[1:-2])

                        data.append([
                            date,
                            reference,
                            description,
                            amount,
                            balance,
                            current_currency
                        ])

    # Build DataFrame
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
