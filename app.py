import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import zipfile
from collections import defaultdict

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
    This tool extracts WIO statement data using **table detection** for maximum reliability. 
    It separates transactions by their unique **IBAN** and **Currency**, ensuring **separate files for two AED accounts** within the same PDF.
    """
)
st.sidebar.markdown("---")
st.sidebar.header("Output Details")
st.sidebar.markdown(
    """
    - **Naming Convention:** Files are named using the Currency and the **last three digits of the IBAN** (e.g., `AED-940.csv`).
    - **Download:** Downloads a `.zip` file containing separate `.csv` files for *each unique bank account*.
    """
)
st.sidebar.info("Tip: The IBAN is the only reliable way to identify separate accounts of the same currency.")


# --- MAIN PAGE CONTENT ---
st.title("WIO Statement Converter & Splitter 🚀")
st.caption("Now using native table extraction and IBAN grouping to solve all known parsing and splitting issues.")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

# --- CORE FUNCTION: EXTRACT TRANSACTIONS USING TABLE DETECTION ---
def extract_transactions(pdf_file):
    data = []
    VALID_CURRENCIES = ["AED", "USD", "EUR", "GBP"]
    current_account_key = None # Key format: IBAN-CURRENCY
    IBAN_REGEX = r"(AE\s*\d{22})" 
    
    # Define table settings based on the WIO statement structure
    table_settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        # These are calculated based on typical WIO statement column positions (Date, Ref, Desc, Amount, Balance)
        "snap_vertical": [0, 80, 150, 480, 600, 720], 
        "intersection_y_tolerance": 5,
    }

    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()

            # STEP 1: ROBUST ACCOUNT KEY FINDER (IBAN + Currency)
            # This logic finds the unique account identifier (IBAN)
            iban_match = re.search(IBAN_REGEX, text)
            currency_match = re.search(r"Balance.*?(" + "|".join(VALID_CURRENCIES) + r")", text, re.IGNORECASE | re.DOTALL)
            
            found_iban = None
            found_currency = None

            if iban_match:
                # Clean the captured IBAN string by removing whitespace
                found_iban = re.sub(r'\s+', '', iban_match.group(1)).strip()
            
            if currency_match:
                found_currency = currency_match.group(1).upper().strip()

            if found_iban and found_currency:
                # Create the unique key: IBAN + Currency (e.g., AE123...-AED)
                current_account_key = f"{found_iban}-{found_currency}"
            
            # Skip transaction parsing if we don't have a key (e.g., summary page)
            if not current_account_key:
                continue

            # STEP 2: TABLE EXTRACTION (Fixes the KeyError issue)
            tables = page.extract_tables(table_settings=table_settings)

            if not tables:
                continue

            for table in tables:
                # The first row is usually the header, so skip it (start at index 1)
                for row in table[1:]:
                    # Clean up data cells: remove newlines and excess spaces
                    cleaned_row = [cell.replace('\n', ' ').strip() if cell else '' for cell in row]
                    
                    # WIO tables usually have 5 or 6 primary columns: Date, Ref, Desc, Amount, Balance
                    # If the row doesn't start with a date, it's likely a continued description or a blank row.
                    if len(cleaned_row) < 5 or not re.match(r"\d{2}[/-]\d{2}[/-]\d{2,4}", cleaned_row[0]):
                        continue
                    
                    try:
                        date = cleaned_row[0]
                        reference = cleaned_row[1]
                        description = cleaned_row[2]
                        
                        # Amount and Balance are the last two columns.
                        # Clean the number strings before conversion
                        amount_str = cleaned_row[-2].replace(',', '').strip()
                        balance_str = cleanedow[-1].replace(',', '').strip()

                        amount = float(amount_str)
                        balance = float(balance_str)
                        
                        # Append transaction with its unique account key information
                        iban, currency = current_account_key.split('-')
                        
                        data.append([
                            date, reference, description, amount, balance, 
                            currency, iban 
                        ])
                    except (ValueError, IndexError):
                        # Safely ignore rows that look like transactions but have invalid numbers
                        continue
                        
    return data

if uploaded_file:
    # Use a try-except block for robust error handling during PDF processing
    try:
        with st.spinner("Analyzing PDF pages and extracting transaction tables..."):
            data = extract_transactions(uploaded_file)
    except Exception as e:
        st.error(f"A critical error occurred during file processing. Please verify the PDF format: {e}")
        st.stop()
        
    # -------------------------------------------
    # STEP 3: SMART DOWNLOAD LOGIC
    # -------------------------------------------
    
    # Check if data is empty to prevent the KeyError
    if not data:
        st.error("❌ No transactions or account keys found in the PDF. The file structure may have changed or the tables could not be detected.")
        st.stop()
        
    # Final DataFrame Creation (No KeyError possible here anymore)
    df = pd.DataFrame(data, columns=["Date", "Reference", "Description", "Amount", "Balance", "Currency", "IBAN"])
    
    st.success(f"✅ Successfully processed {len(df)} transactions, across {len(df['IBAN'].unique())} accounts.")
    
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
            # Ensure the full IBAN is included in the output CSV
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
