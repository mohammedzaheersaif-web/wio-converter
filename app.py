import streamlit as st
import pdfplumber
import pandas as pd
import re

st.title("WIO Bank PDF to CSV Converter (Failsafe Version)")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    data = []
    VALID_CURRENCIES = {"AED", "USD", "EUR", "GBP"}
    
    # Initialize with None
    current_currency = None

    with pdfplumber.open(uploaded_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue

            # -------------------------------------------
            # STEP 1: IMPROVED CURRENCY DETECTION
            # -------------------------------------------
            found_currency = None
            
            # Pattern 1: Table Header "Balance (AED)" - handles newlines
            # Matches: Balance \n (AED)
            header_match = re.search(r"Balance\s*\n?\s*\(\s*([A-Z]{3})\s*\)", text, re.IGNORECASE)
            
            # Pattern 2: Explicit Label "CURRENCY: AED"
            # Matches: CURRENCY \n AED
            label_match = re.search(r"CURRENCY\s*\n?\s*([A-Z]{3})", text, re.IGNORECASE)

            # Pattern 3: Account Name "USD account" (Common in Wio)
            # Matches: USD account
            account_match = re.search(r"\b([A-Z]{3})\s+account\b", text, re.IGNORECASE)

            # Check matches against valid list
            if header_match and header_match.group(1).upper() in VALID_CURRENCIES:
                found_currency = header_match.group(1).upper()
            elif label_match and label_match.group(1).upper() in VALID_CURRENCIES:
                found_currency = label_match.group(1).upper()
            elif account_match and account_match.group(1).upper() in VALID_CURRENCIES:
                found_currency = account_match.group(1).upper()

            # Update persistence variable only if we found something valid
            if found_currency:
                current_currency = found_currency
            
            # -------------------------------------------
            # STEP 2: EXTRACT TRANSACTIONS (Always Run)
            # -------------------------------------------
            lines = text.split("\n")
            
            for line in lines:
                # Date detection (DD/MM/YYYY)
                date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                
                if date_match:
                    date = date_match.group(1)
                    rest_of_line = date_match.group(2).split()

                    # Clean numbers
                    numbers = [p.replace(",", "") for p in rest_of_line if re.match(r"-?\d+(\.\d+)?", p)]

                    # We need at least 2 numbers (Amount and Balance)
                    if len(numbers) >= 2:
                        try:
                            balance = float(numbers[-1])
                            amount = float(numbers[-2])
                            
                            reference = rest_of_line[0]
                            description = " ".join(rest_of_line[1:-2])

                            # SAFETY NET: If currency is still missing, use placeholder
                            # instead of skipping the row.
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
    
    # Alert user if there are unknown currencies
    if "UNKNOWN" in df["Currency"].values:
        st.warning("⚠️ Some transactions have 'UNKNOWN' currency. Please check the CSV manually.")

    st.dataframe(df)

    if not df.empty:
        st.download_button(
            "Download CSV",
            df.to_csv(index=False).encode("utf-8"),
            "wio_transactions.csv",
            "text/csv"
        )
