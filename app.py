import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import zipfile

# Set page configuration
st.set_page_config(page_title="WIO Converter", layout="wide")
st.title("WIO Bank Statement Splitter (CSV Output)")

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
            # STEP 1: ROBUST CURRENCY FINDER (Unchanged)
            # -------------------------------------------
            found_currency = None
            
            # Search strategies (using re.DOTALL to span across newlines)
            balance_match = re.search(r"Balance.*?(" + "|".join(VALID_CURRENCIES) + r")", text, re.IGNORECASE | re.DOTALL)
            account_match = re.search(r"\b(" + "|".join(VALID_CURRENCIES) + r")\s+Account\b", text, re.IGNORECASE)
            currency_lbl_match = re.search(r"CURRENCY.*?(" + "|".join(VALID_CURRENCIES) + r")", text, re.IGNORECASE | re.DOTALL)

            if balance_match:
                found_currency = balance_match.group(1).upper()
            elif account_match:
                found_currency = account_match.group(1).upper()
            elif currency_lbl_match:
                found_currency = currency_lbl_match.group(1).upper()

            if found_currency:
                current_currency = found_currency

            # -------------------------------------------
            # STEP 2: EXTRACT TRANSACTIONS (Unchanged)
            # -------------------------------------------
            lines = text.split("\n")
            for line in lines:
                # Date detection
                date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                
                if date_match:
                    date = date_match.group(1)
                    rest_of_line = date_match.group(2).split()
                    # Clean and find numbers
                    numbers = [p.replace(",", "") for p in rest_of_line if re.match(r"-?\d+(\.\d+)?", p)]

                    if len(numbers) >= 2:
                        try:
                            # Assign Amount and Balance (last two numbers)
                            balance = float(numbers[-1])
                            amount = float(numbers[-2])
                            
                            reference = rest_of_line[0]
                            description = " ".join(rest_of_line[1:-2])
                            row_currency = current_currency if current_currency else "UNKNOWN"

                            data.append([date, reference, description, amount, balance, row_currency])
                        except ValueError:
                            continue

    # -------------------------------------------
    # STEP 3: SMART DOWNLOAD LOGIC (Now using CSV)
    # -------------------------------------------
    df = pd.DataFrame(data, columns=["Date", "Reference", "Description", "Amount", "Balance", "Currency"])

    if not df.empty:
        st.success(f"Processed {len(df)} transactions.")
        st.dataframe(df)

        unique_currencies = df["Currency"].unique()
        
        # Function to generate CSV data
        def generate_csv_data(df_to_write):
            # df.to_csv() generates the CSV data as a string, encode it to bytes
            return df_to_write.to_csv(index=False).encode('utf-8')


        # CASE A: Only one currency found -> Download single CSV file
        if len(unique_currencies) == 1:
            currency_name = unique_currencies[0]
            
            st.download_button(
                label=f"Download {currency_name}.csv",
                data=generate_csv_data(df),
                file_name=f"{currency_name}.csv",
                mime="text/csv" # MIME type for CSV
            )

        # CASE B: Multiple currencies found -> Download as ZIP containing CSVs
        else:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for curr in unique_currencies:
                    subset_df = df[df["Currency"] == curr]
                    
                    csv_data = generate_csv_data(subset_df)
                    
                    # Name the file inside the zip with .csv extension
                    zf.writestr(f"{curr}.csv", csv_data)

            st.download_button(
                label="Download All (ZIP of CSVs)",
                data=zip_buffer.getvalue(),
                file_name="Wio_Statements.zip",
                mime="application/zip"
            )
            
    else:
        st.warning("No transactions found. Please check the PDF.")
