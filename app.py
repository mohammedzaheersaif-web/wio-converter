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

            # ------------------------------------------------
            # STEP 1: Detect currency by scanning entire page
            # ------------------------------------------------
            for i, line in enumerate(lines):

                # format 1:
                # CURRENCY
                # AED
                if line.strip() == "CURRENCY" and i + 1 < len(lines):
                    nxt = lines[i + 1].strip()
                    if nxt in valid_currencies:
                        current_currency = nxt

                # format 2: CURRENCY AED
                if "CURRENCY" in line:
                    for word in line.split():
                        if word in valid_currencies:
                            current_currency = word

            # if still None, default to AED (optional)
            if current_currency is None:
                current_currency = "AED"

            # ------------------------------------------------
            # STEP 2: Extract transactions
            # ------------------------------------------------
            for line in lines:

                date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                if date_match:
                    date = date_match.group(1)
                    rest = date_match.group(2).split()

                    # extract numbers (amount + balance)
                    numbers = [p.replace(",", "") for p in rest if re.match(r"-?\d+(\.\d+)?", p)]

                    if len(numbers) >= 2:
                        amount = float(numbers[-2])
                        balance = float(numbers[-1])

                        description = " ".join(rest[:-2])

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

    st.download_button("Download CSV", csv, "wio_transactions.csv", "text/csv")
