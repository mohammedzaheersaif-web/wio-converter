import streamlit as st
import pdfplumber
import pandas as pd
import re

st.title("WIO Bank PDF to CSV Converter (Strict Currency Fix)")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    data = []
    
    # -------------------------------------------
    # CRITICAL FIX: STRICT VALIDATION LIST
    # The script will now REJECT "DSO", "FZCO", "UAE", etc.
    # -------------------------------------------
    VALID_CURRENCIES = {"AED", "USD", "EUR", "GBP"}
    
    # Default to None so we don't guess unless we are sure
    current_currency = None

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            # -------------------------------------------
            # STEP 1: FIND CURRENCY (With Validation)
            # -------------------------------------------
            # Strategy A: Look for "Balance (XXX)" in the table header
            # This is the most accurate location for Wio statements.
            header_match = re.search(r"Balance\s*\n?\s*\(\s*([A-Z]{3})\s*\)", text, re.IGNORECASE)
            
            # Strategy B: Look for explicit "CURRENCY XXX" label
            label_match = re.search(r"CURRENCY\s*\n?\s*([A-Z]{3})", text, re.IGNORECASE)

            found_currency = None

            if header_match:
                candidate = header_match.group(1).upper()
                if candidate in VALID_CURRENCIES:
                    found_currency = candidate
            
            # If Strategy A failed, try Strategy B
            if not found_currency and label_match:
                candidate = label_match.group(1).upper()
                if candidate in VALID_CURRENCIES:
                    found_currency = candidate
            
            # Update current_currency ONLY if we found a valid one.
            # Otherwise, keep the one from the previous page (for multi-page statements).
            if found_currency:
                current_currency = found_currency
            
            # If we still don't have a currency (e.g. Page 1 summary), skip transactions or default
            if not current_currency:
                # You can default to AED if you prefer, but it's safer to wait for detection
                pass 

            # -------------------------------------------
            # STEP 2: EXTRACT TRANSACTIONS
            # -------------------------------------------
            lines = text.split("\n")
            
            for line in lines:
                # Date detection (DD/MM/YYYY)
                date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                
                if date_match and current_currency:
                    date = date_match.group(1)
                    rest_of_line = date_match.group(2).split()

                    # Filter for valid numbers (remove commas)
                    numbers = [p.replace(",", "") for p in rest_of_line if re.match(r"-?\d+(\.\d+)?", p)]

                    # We need at least 2 numbers (Amount and Balance)
                    if len(numbers) >= 2:
                        try:
                            balance = float(numbers[-1])
                            amount = float(numbers[-2])
                            
                            reference = rest_of_line[0]
                            
                            # Join the description parts
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

    # -------------------------------------------
    # STEP 3: OUTPUT
    # -------------------------------------------
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
