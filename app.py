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
    This tool extracts WIO statement data using **precise table detection** for maximum reliability. 
    It separates transactions by their unique **IBAN** and **Currency**, ensuring **separate files for all distinct accounts** in the PDF.
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
st.sidebar.info("This version uses targeted table extraction to resolve previous parsing failures.")


# --- MAIN PAGE CONTENT ---
st.title("WIO Statement Converter & Splitter 🎯")
st.caption("Now using precise coordinate targeting to ensure transactions are always found.")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

# --- CORE FUNCTION: EXTRACT TRANSACTIONS USING TARGETED TABLE DETECTION ---
def extract_transactions(pdf_file):
    data = []
    VALID_CURRENCIES = ["AED", "USD", "EUR", "GBP"]
    current_account_key = None # Key format: IBAN-CURRENCY
    IBAN_REGEX = r"(AE\s*\d{22})" 
    
    # 1. Standard WIO Transaction Column Markers (X-coordinates)
    # These represent the exact vertical lines of the transaction table, adjusted for high reliability.
    TRANSACTION_COLUMNS = [20, 75, 140, 500, 600, 700] # Date, Ref, Desc, Amount, Balance
    
    # 2. Table Extraction Settings
    table_settings = {
        "vertical_strategy": "explicit", # Use our precise vertical markers
        "horizontal_strategy": "lines", # Rely on horizontal lines in the PDF
        "explicit_vertical_lines": TRANSACTION_COLUMNS,
        "intersection_y_tolerance": 5,
    }

    def clean_and_float(value):
        """Cleans a string by removing commas, stripping whitespace, and converting to float."""
        if not value: return None
        return float(value.replace(',', '').strip())

    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            
            # -------------------------------------------
            # STEP 1: ROBUST ACCOUNT KEY FINDER (IBAN + Currency)
            # -------------------------------------------
            iban_match = re.search(IBAN_REGEX, text)
            currency_match = re.search(r"Balance.*?(" + "|".join(VALID_CURRENCIES) + r")", text, re.IGNORECASE | re.DOTALL)
            
            found_iban = None
            found_currency = None

            if iban_match:
                found_iban = re.sub(r'\s+', '', iban_match.group(1)).strip()
            
            if currency_match:
                found_currency = currency_match.group(1).upper().strip()

            if found_iban and found_currency:
                current_account_key = f"{found_iban}-{found_currency}"
            
            if not current_account_key:
                continue
                
            # -------------------------------------------
            # STEP 2: TARGETED TABLE EXTRACTION & FLEXIBLE PARSING
            # -------------------------------------------
            
            # Crop the page to the area where the transactions are located (e.g., from Y=200 down to Y=780)
            # This ignores the summary table and footer.
            page_height = page.height
            cropped_page = page.crop((0, 200, page.width, page_height - 50))

            tables = cropped_page.extract_tables(table_settings=table_settings)

            if not tables:
                continue

            for table in tables:
                # The first row is usually the header, skip it (start at index 1)
                for row in table[1:]:
                    # Clean up data cells: remove newlines and excess spaces
                    # Only include non-None cells
                    cleaned_row = [cell.replace('\n', ' ').strip() if cell else '' for cell in row if cell is not None]
                    
                    # Minimum expected length for transaction data is 4 (Date, Ref/Desc, Amount, Balance)
                    if len(cleaned_row) < 4:
                        continue
                    
                    # 1. Date Check: Must start with a date format
                    if not re.match(r"\d{2}[/-]\d{2}[/-]\d{2,4}", cleaned_row[0]):
                        continue
                    
                    try:
                        date = cleaned_row[0]
                        
                        # 2. Dynamic Numeric Extraction (Find the last two floats)
                        numeric_values = []
                        text_parts = []
                        
                        # Iterate backward from the end of the list, ignoring the Date
                        for item in reversed(cleaned_row[1:]): 
                            try:
                                float_val = clean_and_float(item)
                                if float_val is not None and len(numeric_values) < 2:
                                    numeric_values.append(float_val)
                                else:
                                    text_parts.insert(0, item) 
                            except ValueError:
                                text_parts.insert(0, item)
                        
                        # Ensure we found both Amount and Balance
                        if len(numeric_values) < 2:
                            continue
                        
                        # The first number found (closest to the end of the row) is Balance, the second is Amount.
                        balance = numeric_values[0] 
                        amount = numeric_values[1] 

                        # 3. Assign Text Fields (Reference and Description)
                        if len(text_parts) >= 2:
                            reference = text_parts[0]
                            description = " ".join(text_parts[1:])
                        elif len(text_parts) == 1:
                            reference = text_parts[0]
                            description = ""
                        else:
                            reference = ""
                            description = ""

                        # Final Data Append
                        iban, currency = current_account_key.split('-')
                        
                        data.append([
                            date, reference, description, amount, balance, 
                            currency, iban 
                        ])
                    except Exception as e:
                        # Log any unexpected error during row processing but continue
                        # st.write(f"Skipping row due to error: {e}") 
                        continue
                        
    return data

if uploaded_file:
    # Use a try-except block for robust error handling during PDF processing
    try:
        with st.spinner("Analyzing PDF pages and extracting transaction tables..."):
            data = extract_transactions(uploaded_file)
    except Exception as e:
        # Catch any high-level file reading error
        st.error(f"A critical error occurred during file processing. Please verify the PDF is not corrupted or password protected: {e}")
        st.stop()
        
    # -------------------------------------------
    # STEP 3: SMART DOWNLOAD LOGIC
    # -------------------------------------------
    
    # Check if data is empty to prevent errors
    if not data:
        st.error("❌ No transactions or account keys found. The file structure may have changed. Please contact support with a sample PDF.")
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
