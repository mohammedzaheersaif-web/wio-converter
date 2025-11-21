import streamlit as st
import pdfplumber
import pandas as pd
import re

st.title("WIO Bank PDF to CSV Converter (Fixed Currency)")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    data = []
    
    # We will use this to remember currency if a page has transactions 
    # but lacks a header (unlikely in Wio, but good for safety).
    current_currency = "AED" 

    with pdfplumber.open(uploaded_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue

            # -------------------------------------------
            # STEP 1: ROBUST CURRENCY DETECTION
            # -------------------------------------------
            # Strategy: Look for the Transaction Table Header first. 
            # In your PDF, it appears as "Balance (AED)" or "Balance \n (AED)"
            # See Reference [51] in your file.
            
            # Search the WHOLE text block, not just line by line, to handle newlines
            header_match = re.search(r"Balance\s*\n?\s*\(([A-Z]{3})\)", text, re.IGNORECASE)
            
            if header_match:
                current_currency = header_match.group(1).upper()
            else:
                # Fallback: Look for "GBP account" or "USD account" labels 
                # commonly found in the account details section [cite: 82, 123]
                account_match = re.search(r"\b([A-Z]{3})\s+account\b", text, re.IGNORECASE)
                if account_match:
                    current_currency = account_match.group(1).upper()

            # -------------------------------------------
            # STEP 2: EXTRACT TRANSACTIONS
            # -------------------------------------------
            lines = text.split("\n")
            
            for line in lines:
                # Date detection (DD/MM/YYYY)
                date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                
                if date_match:
                    date = date_match.group(1)
                    rest_of_line = date_match.group(2).split()

                    # Filter for numbers (amounts and balances)
                    # We remove commas to convert "1,000.00" -> 1000.00
                    numbers = [p.replace(",", "") for p in rest_of_line if re.match(r"-?\d+(\.\d+)?", p)]

                    # We need at least 2 numbers (Amount and Balance)
                    if len(numbers) >= 2:
                        try:
                            # The last number is the Running Balance
                            balance = float(numbers[-1])
                            # The second to last number is the Transaction Amount
                            amount = float(numbers[-2])
                            
                            # Reference is usually the first item after the date
                            reference = rest_of_line[0]
                            
                            # Description is everything in between
                            # We join the parts that are NOT the reference and NOT the last 2 numbers
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
    # STEP 3: DISPLAY & DOWNLOAD
    # -------------------------------------------
    df = pd.DataFrame(data, columns=[
        "Date", "Reference", "Description", "Amount", "Balance", "Currency"
    ])

    st.write(f"### Extracted {len(df)} Transactions")
    
    # Optional: Display data grouped by Currency to verify it worked
    if not df.empty:
        st.write("Summary by Currency:")
        st.write(df.groupby("Currency")["Amount"].count())
        
    st.dataframe(df)

    if not df.empty:
        st.download_button(
            "Download CSV",
            df.to_csv(index=False).encode("utf-8"),
            "wio_transactions.csv",
            "text/csv"
        )
