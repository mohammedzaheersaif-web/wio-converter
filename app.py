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

            # Detect currency for this page FIRST
            page_currency = None
            for i, line in enumerate(lines):

                # Case 1: "CURRENCY AED"
                m = re.search(r"CURRENCY\s+([A-Z]{3})", line)
                if m:
                    code = m.group(1).upper()
                    if code in valid_currencies:
                        page_currency = code

                # Case 2: "CURRENCY" + next line "AED"
                if line.strip() == "CURRENCY" and i + 1 < len(lines):
                    nxt = lines[i + 1].strip()
                    if nxt in valid_currencies:
                        page_currency = nxt

                # Case 3: "EUR account"
                acc_m = re.match(r"^([A-Z]{3}) account$", line.strip())
                if acc_m:
                    code = acc_m.group(1).upper()
                    if code in valid_currencies:
                        page_currency = code

            # If currency detected — switch context
            if page_currency:
                current_currency = page_currency

            # If still no currency — skip this page entirely
            if current_currency is None:
                continue

            # Extract transactions AFTER correct currency set
            temp_rows = []
            for line in lines:
                m = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                if not m:
                    continue

                date = m.group(1)
                body = m.group(2).split()

                # Extract numeric values: amount + balance
                nums = [x.replace(",", "") for x in body if re.match(r"-?\d+(\.\d+)?$", x)]
                if len(nums) < 2:
                    continue

                amount = float(nums[-2])
                balance = float(nums[-1])

                reference = body[0]
                description = " ".join(body[1:-2])

                temp_rows.append([
                    date, reference, description,
                    amount, balance, current_currency
                ])

            # Skip USD blocks with NO transactions (your rule B)
            if len(temp_rows) == 0:
                continue

            data.extend(temp_rows)

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
