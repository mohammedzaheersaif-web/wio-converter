import streamlit as st
import pdfplumber
import pandas as pd
import re

st.title("WIO Bank PDF to CSV Converter (Multi-Page Support)")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    data = []
    valid_currencies = ["AED", "USD", "EUR", "GBP"]

    # -------------------------------------------
    # CHANGE: Initialize currency OUTSIDE the loop
    # Default to AED. If a specific currency is found,
    # it will update and persist for subsequent pages.
    # -------------------------------------------
    current_currency = "AED"

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split("\n")

            # -------------------------------------------
            # STEP 1: CHECK FOR CURRENCY CHANGE
            # -------------------------------------------
            for i, line in enumerate(lines):
                # Case 1: Format: CURRENCY GBP
                match = re.search(r"CURRENCY\s+([A-Z]{3})", line)
                if match:
                    found = match.group(1)
                    if found in valid_currencies:
                        current_currency = found
                    continue

                # Case 2: Line: CURRENCY (and next line is code)
                if line.strip() == "CURRENCY" and i + 1 < len(lines):
                    nxt = lines[i + 1].strip()
                    if nxt in valid_currencies:
                        current_currency = nxt
                    continue

                # Case 3: Format: "USD account", "GBP account"
                acc_match = re.match(r"^([A-Z]{3})\s+account$", line.strip())
                if acc_match:
                    found = acc_match.group(1)
                    if found in valid_currencies:
                        current_currency = found
                    continue
            
            # Note: We removed the "if current_currency is None" check here.
            # We now rely on the value persisting from previous pages.

            # -------------------------------------------
            # STEP 2: EXTRACT TRANSACTIONS
            # -------------------------------------------
            for line in lines:
                # Date detection (DD/MM/YYYY or DD-MM-YYYY)
                date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                
                if date_match:
                    date = date_match.group(1)
                    rest_of_line = date_match.group(2).split()

                    # Extract amount + balance
                    numbers = [p.replace(",", "") for p in rest_of_line if re.match(r"-?\d+(\.\d+)?", p)]

                    if len(numbers) >= 2:
                        try:
                            amount = float(numbers[-2])
                            balance = float(numbers[-1])
                            
                            # Reference number = first token
                            reference = rest_of_line[0]
                            
                            # Description = tokens between Ref and Amounts
                            description = " ".join(rest_of_line[1:-2])

                            data.append([
                                date,
                                reference,
                                description,
                                amount,
                                balance,
                                current_currency
                            ])
                        except ValueError:
                            continue

    # Create DataFrame
    df = pd.DataFrame(data, columns=[
        "Date", "Reference", "Description", "Amount", "Balance", "Currency"
    ])

    st.write(f"### Extracted {len(df)} Transactions")
    st.dataframe(df)

    if not df.empty:
        st.download_button(
            "Download CSV",
            df.to_csv(index=False).encode("utf-8"),
            "wio_transactions.csv",
            "text/csv"
        )
