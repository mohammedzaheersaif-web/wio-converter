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
        current_currency = None

        for page in pdf.pages:

            text = page.extract_text()
            if not text:
                continue

            lines = text.split("\n")

            # ------------------------------------------------------
            # UNIVERSAL + STRICT CURRENCY DETECTION (Your PDF exact)
            # ------------------------------------------------------
            for i, line in enumerate(lines):

                # Case A: "CURRENCY <code>"
                match = re.search(r"CURRENCY\s+([A-Z]{3})", line.strip())
                if match:
                    code = match.group(1)
                    if code in valid_currencies:
                        current_currency = code
                    continue

                # Case B: "CURRENCY" then next line is code
                if line.strip() == "CURRENCY" and i + 1 < len(lines):
                    nxt = lines[i + 1].strip()
                    if nxt in valid_currencies:
                        current_currency = nxt
                    continue

                # Case C: "USD account", "GBP account", etc.
                acc_match = re.match(r"^([A-Z]{3})\s+account$", line.strip())
                if acc_match:
                    code = acc_match.group(1)
                    if code in valid_currencies:
                        current_currency = code
                    continue

            # SAFETY fallback
            if current_currency is None:
                current_currency = "AED"

            # ------------------------------------------------------
            # EXTRACT TRANSACTIONS
            # ------------------------------------------------------
            for line in lines:

                # WIO transaction lines always start with date
                date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                if not date_match:
                    continue

                date = date_match.group(1)
                rest = date_match.group(2).split()

                # Grab numbers (amount, balance)
                numbers = [p.replace(",", "") for p in rest if re.match(r"-?\d+(\.\d+)?", p)]
                if len(numbers) < 2:
                    continue

                amount = float(numbers[-2])
                balance = float(numbers[-1])

                # Reference = first word after date
                reference = rest[0]

                # Description = everything until amount
                description = " ".join(rest[1:-2])

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
