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

        for i, page in enumerate(pdf.pages):

            text = page.extract_text()
            if not text:
                continue

            lines = [l.strip() for l in text.split("\n") if l.strip()]

            # Extract currency ONCE from the page header
            current_currency = None
            for j, line in enumerate(lines):

                if line == "CURRENCY" and j+1 < len(lines):
                    next_line = lines[j+1].strip()
                    if next_line in valid_currencies:
                        current_currency = next_line
                        break

                m = re.search(r"CURRENCY\s+([A-Z]{3})", line)
                if m and m.group(1) in valid_currencies:
                    current_currency = m.group(1)
                    break

            # Skip pages without currency OR no transaction table
            if not current_currency:
                continue

            # Extract transactions on this page
            for line in lines:
                m = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                if not m:
                    continue

                date = m.group(1)
                parts = m.group(2).split()

                nums = [p.replace(",", "") for p in parts if re.match(r"-?\d+(\.\d+)?$", p)]
                if len(nums) < 2:
                    continue

                amount = float(nums[-2])
                balance = float(nums[-1])
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

    st.dataframe(df)
    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), "wio.csv")
