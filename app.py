import streamlit as st
import pdfplumber
import pandas as pd
import re

st.title("WIO Bank PDF to CSV Converter")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    valid_currencies = ["AED", "USD", "EUR", "GBP"]
    page_currency = {}

    with pdfplumber.open(uploaded_file) as pdf:

        # ----- PASS 1: Detect currency per page -----
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            lines = text.split("\n")

            for j, line in enumerate(lines):

                m = re.search(r"CURRENCY\s+([A-Z]{3})", line)
                if m and m.group(1) in valid_currencies:
                    page_currency[i] = m.group(1)
                    break

                if line.strip() == "CURRENCY" and j + 1 < len(lines):
                    nxt = lines[j + 1].strip()
                    if nxt in valid_currencies:
                        page_currency[i] = nxt
                        break

        # Carry currency forward
        last_currency = None
        for i in range(len(pdf.pages)):
            if i in page_currency:
                last_currency = page_currency[i]
            else:
                page_currency[i] = last_currency

        # ----- PASS 2: Extract transactions -----
        data = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            lines = text.split("\n")

            current_currency = page_currency.get(i)

            if current_currency is None:
                continue

            for line in lines:
                match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                if not match:
                    continue

                date = match.group(1)
                body = match.group(2).split()

                nums = [x.replace(",", "") for x in body if re.match(r"-?\d+(\.\d+)?$", x)]
                if len(nums) < 2:
                    continue

                amount = float(nums[-2])
                balance = float(nums[-1])

                reference = body[0]
                description = " ".join(body[1:-2])

                data.append([date, reference, description, amount, balance, current_currency])

    df = pd.DataFrame(data, columns=["Date", "Reference", "Description", "Amount", "Balance", "Currency"])

    st.dataframe(df)
    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), "wio.csv")
