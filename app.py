import streamlit as st
import pdfplumber
import pandas as pd
import re

st.title("WIO Bank PDF to CSV Converter")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    data = []
    VALID_CURRENCIES = ["AED", "USD", "EUR", "GBP"]
    current_currency = None

    with pdfplumber.open(uploaded_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue

            # -------------------------------------------
            # STEP 1: ROBUST CURRENCY FINDER
            # -------------------------------------------
            found_currency = None

            # STRATEGY 1: "Balance" Header (Most Reliable for Transactions)
            # Looks for "Balance" followed by any characters (newlines/spaces) then a valid currency.
            # Example matches: "Balance (AED)", "Balance\n(USD)", "Balance ... GBP"
            balance_match = re.search(r"Balance.*?(" + "|".join(VALID_CURRENCIES) + r")", text, re.IGNORECASE | re.DOTALL)
            
            # STRATEGY 2: "Currency" Label
            # Matches "Currency: AED", "Currency \n USD"
            currency_lbl_match = re.search(r"CURRENCY.*?(" + "|".join(VALID_CURRENCIES) + r")", text, re.IGNORECASE | re.DOTALL)
            
            # STRATEGY 3: "Account" Title
            # Matches "USD Account", "GBP Account"
            account_match = re.search(r"\b(" + "|".join(VALID_CURRENCIES) + r")\s+Account\b", text, re.IGNORECASE)

            # Prioritize matches
            if balance_match:
                found_currency = balance_match.group(1).upper()
            elif account_match:
                found_currency = account_match.group(1).upper()
            elif currency_lbl_match:
                found_currency = currency_lbl_match.group(1).upper()

            # Update persistent currency if a new one is found on this page
            if found_currency:
                current_currency = found_currency

            # -------------------------------------------
            # STEP 2: EXTRACT TRANSACTIONS
            # -------------------------------------------
            lines = text.split("\n")
            
            for line in lines:
                # 1. Detect Date (DD/MM/YYYY)
                date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                
                if date_match:
                    date = date_match.group(1)
                    rest_of_line = date_match.group(2).split()

                    # 2. Extract Numbers (Amount & Balance)
                    # Filter for things that look like numbers (allow negative, decimals)
                    numbers = [p.replace(",", "") for p in rest_of_line if re.match(r"-?\d+(\.\d+)?", p)]

                    # We need at least 2 numbers: [Amount, Balance]
                    if len(numbers) >= 2:
                        try:
                            balance = float(numbers[-1])  # Last number is Balance
                            amount = float(numbers[-2])   # Second to last is Amount
                            
                            # 3. Extract Text Details
                            reference = rest_of_line[0] # First text item is Ref
                            description = " ".join(rest_of_line[1:-2]) # Everything in between

                            # 4. Assign Currency
                            # Use "UNKNOWN" if detection failed completely to avoid empty table
                            row_currency = current_currency if current_currency else "UNKNOWN"

                            data.append([
                                date,
                                reference,
                                description,
                                amount,
                                balance,
                                row_currency
                            ])
                        except ValueError:
                            continue

    # -------------------------------------------
    # STEP 3: DISPLAY & DOWNLOAD
    # -------------------------------------------
    df = pd.DataFrame(data, columns=[
        "Date", "Reference", "Description", "Amount", "Balance", "Currency"
    ])

    st.write(f"### Extracted {len(df)} Transactions")
    
    if "UNKNOWN" in df["Currency"].values:
        st.warning("⚠️ Some currencies could not be identified automatically. Please check the CSV.")

    st.dataframe(df)

    if not df.empty:
        st.download_button(
            "Download CSV",
            df.to_csv(index=False).encode("utf-8"),
            "wio_transactions.csv",
            "text/csv"
        )

