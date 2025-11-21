import streamlit as st
import pdfplumber
import pandas as pd
import re

st.title("WIO Bank PDF to CSV Converter")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    data = []
    current_currency = None  # track currency for each account block

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split("\n")

            for line in lines:

                # Detect currency section (example: CURRENCY AED)
                if "CURRENCY" in line:
                    parts = line.split()
                    try:
                        idx = parts.index("CURRENCY")
                        current_currency = parts[idx + 1].strip()
                    except:
                        pass

                # Match date lines: DD/MM/YYYY or DD-MM-YYYY
                date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                if date_match:
                    date = date_match.group(1)
                    remaining = date_match.group(2).split()

                    # Extract amount & balance (last 2 numbers)
                    numbers = [p.replace(",", "") for p in remaining if re.match(r"-?\d+(\.\d+)?", p)]

                    if len(numbers) >= 2:
                        amount = float(numbers[-2])
                        balance = float(numbers[-1])

                        # Debit must be negative
                        if amount > 0 and "-" in remaining:
                            amount = -abs(amount)

                        # Description = everything except date, ref, amount, balance
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
