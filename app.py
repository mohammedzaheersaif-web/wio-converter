import streamlit as st
import pdfplumber
import pandas as pd
import re

st.title("WIO Bank PDF to CSV Converter")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    all_rows = []
    last_currency = "AED"
    valid_curr = ["AED","USD","EUR","GBP"]

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:

            # Detect currency inside table header
            extracted = page.extract_text()
            if extracted:
                cur_find = re.search(r"Balance\s*\((\w{3})\)", extracted, re.IGNORECASE)
                if cur_find:
                    cur = cur_find.group(1).upper()
                    if cur in valid_curr:
                        last_currency = cur

            # Extract tables correctly (instead of free-text)
            tables = page.extract_tables()

            for table in tables:
                df = pd.DataFrame(table)

                # Try to detect correct header row
                for idx, row in df.iterrows():
                    if (
                        "Date" in row.values
                        and "Balance" in row.values
                        and "Amount" in row.values
                    ):
                        df.columns = row
                        df = df[idx + 1:]
                        break
                else:
                    continue

                # Clean columns only if correct structure
                if set(["Date","Amount","Balance"]).issubset(df.columns):

                    df["Currency"] = last_currency

                    df["Date"] = df["Date"].str.extract(r"(\d{2}[/-]\d{2}[/-]\d{4})")

                    df["Amount"] = (
                        df["Amount"]
                        .str.replace(",", "", regex=False)
                        .astype(str)
                        .str.extract(r"(-?\d+\.?\d*)")
                    )

                    df["Balance"] = (
                        df["Balance"]
                        .str.replace(",", "", regex=False)
                        .astype(str)
                        .str.extract(r"(\d+\.?\d*)")
                    )

                    df.replace("", pd.NA, inplace=True)
                    df.dropna(subset=["Date"], inplace=True)

                    all_rows.append(df)

    if all_rows:
        final_df = pd.concat(all_rows, ignore_index=True)
    else:
        final_df = pd.DataFrame(columns=["Date","Reference","Description","Amount","Balance","Currency"])

    st.dataframe(final_df)

    st.download_button(
        "Download CSV",
        final_df.to_csv(index=False).encode("utf-8"),
        "wio_transactions.csv",
        "text/csv"
    )
