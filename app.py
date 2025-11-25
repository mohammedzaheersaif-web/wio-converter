import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import zipfile
import csv # New: Using Python's built-in CSV parser

# --- APP CONFIGURATION ---
st.set_page_config(
    page_title="WIO Statement Splitter", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SIDEBAR (For Instructions & Cleanliness) ---
st.sidebar.title("⚙️ How to Use")
st.sidebar.markdown(
    """
    This tool extracts WIO statement data by treating the raw PDF text as a **quoted CSV file**. This is the most resilient method for this document type.
    """
)
st.sidebar.markdown("---")
st.sidebar.header("Output Details")
st.sidebar.markdown(
    """
    - **Naming:** Files are named using the Currency and the **last three digits of the IBAN** (e.g., `AED-940.csv`).
    - **Splitting:** Accounts of the same currency (e.g., two AED accounts) are split into separate files based on their unique IBAN.
    """
)
st.sidebar.info("This version completely bypasses unreliable table detection by using direct CSV parsing on the raw text.")


# --- MAIN PAGE CONTENT ---
st.title("WIO Statement Converter & Splitter 🚀")
st.caption("Using raw text extraction and CSV parsing for maximum reliability.")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

# --- CORE FUNCTION: EXTRACT TRANSACTIONS USING PURE TEXT/CSV PARSING ---
def extract_transactions(pdf_file):
    data = []
    VALID_CURRENCIES = ["AED", "USD", "EUR", "GBP"]
    current_account_key = None # Key format: IBAN-CURRENCY
    IBAN_REGEX = r"(AE\s*\d{22})" 
    
    # Standard WIO transaction header pattern
    HEADER_PATTERN = re.compile(r'"Date"\s*,\s*"Ref\. Number"\s*,\s*"Description"\s*,\s*"Amount\s*\(Incl\. VAT\)"\s*,\s*"Balance\s*\((\w+)\)"', re.IGNORECASE)
    
    def clean_and_float(value):
        """Cleans a string by removing commas, stripping whitespace, and converting to float."""
        if not value: return None
        return float(value.replace(',', '').strip())

    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # Extract raw text from the entire page
            raw_text = page.extract_text()
            
            # -------------------------------------------
            # STEP 1: ROBUST ACCOUNT KEY FINDER (IBAN + Currency)
            # -------------------------------------------
            # Find the IBAN anywhere on the page
            iban_match = re.search(IBAN_REGEX, raw_text)
            
            found_iban = None
            found_currency = None

            if iban_match:
                found_iban = re.sub(r'\s+', '', iban_match.group(1)).strip()
            
            # The currency is usually found in the balance section near the IBAN/Account details
            currency_match = re.search(r"Balance.*?(" + "|".join(VALID_CURRENCIES) + r")", raw_text, re.IGNORECASE | re.DOTALL)
            if currency_match:
                found_currency = currency_match.group(1).upper().strip()

            if found_iban and found_currency:
                current_account_key = f"{found_iban}-{found_currency}"
            
            if not current_account_key:
                continue

            # -------------------------------------------
            # STEP 2: PURE TEXT/CSV EXTRACTION (Bypasses Table Detection)
            # -------------------------------------------
            
            # Find the starting position of the transaction table header
            header_match = HEADER_PATTERN.search(raw_text)
            
            if header_match:
                # Get the text starting right after the header line
                transactions_block = raw_text[header_match.end():]
                
                # Stop parsing when we hit the footer/disclaimer text
                transactions_block = transactions_block.split("Please review this account statement")[0]
                
                # Use Python's built-in CSV reader to parse the text block
                f = io.StringIO(transactions_block)
                reader = csv.reader(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

                for row in reader:
                    # Filter out empty rows or rows that are too short (less than 5 expected fields)
                    row = [col.replace('\n', ' ').strip() for col in row if col.strip() != '']
                    
                    if len(row) < 5 or not re.match(r"\d{2}[/-]\d{2}[/-]\d{2,4}", row[0]):
                        continue

                    # Expected columns: Date, Ref. Number, Description, Amount (Incl. VAT), Balance
                    try:
                        date = row[0]
                        reference = row[1]
                        # Description might span multiple text columns, so join everything before the last two (Amount/Balance)
                        description = row[2] 
                        
                        # Amount and Balance are the last two columns.
                        amount = clean_and_float(row[-2])
                        balance = clean_and_float(row[-1])
                        
                        if amount is None or balance is None:
                            continue

                        iban, currency = current_account_key.split('-')
                        
                        data.append([
                            date, reference, description, amount, balance, 
                            currency, iban 
                        ])
                    except Exception:
                        # Skip if any conversion or indexing error occurs
                        continue
                        
    return data

if uploaded_file:
    # Use a try-except block for robust error handling during PDF processing
    try:
        with st.spinner("Analyzing PDF pages and parsing data block..."):
            data = extract_transactions(uploaded_file)
    except Exception as e:
        st.error(f"A critical error occurred during file processing: {e}. The file may be corrupt or not a standard WIO statement.")
        st.stop()
        
    # -------------------------------------------
    # STEP 3: SMART DOWNLOAD LOGIC
    # -------------------------------------------
    
    if not data:
        st.error("❌ No transactions or account keys found. The CSV-like transaction data could not be located in the raw text.")
        st.stop()
        
    # Final DataFrame Creation
    df = pd.DataFrame(data, columns=["Date", "Reference", "Description", "Amount", "Balance", "Currency", "IBAN"])
    
    st.success(f"✅ Successfully processed {len(df)} transactions, across {len(df['IBAN'].unique())} unique account(s).")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("Data Preview")
        # Display the unique IBANs found for verification
        st.info("Found Accounts: " + ", ".join([f"{c} ({i[-4:]})" for i, c in df[['IBAN', 'Currency']].drop_duplicates().values]))
        st.dataframe(df.drop(columns=['IBAN']), use_container_width=True)

    with col2:
        st.subheader("Download Files")
        # Use IBAN + Currency for unique grouping key
        unique_account_keys = df["IBAN"] + "-" + df["Currency"]
        
        def generate_csv_data(df_to_write):
            return df_to_write.to_csv(index=False).encode('utf-8')

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for account_key in unique_account_keys.unique():
                iban, currency = account_key.split('-')
                subset_df = df[(df["IBAN"] == iban) & (df["Currency"] == currency)].copy()
                
                csv_data = generate_csv_data(subset_df)
                
                # File Naming: Currency-Last3DigitsOfIBAN.csv (e.g., AED-940.csv)
                file_name = f"{currency}-{iban[-3:]}.csv"
                zf.writestr(file_name, csv_data)

            st.download_button(
                label=f"📦 Download All {len(unique_account_keys.unique())} Accounts (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="Wio_Statements_Split_by_Account.zip",
                mime="application/zip",
                key='multi_account_download'
            )
