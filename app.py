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
    It separates transactions by their unique **IBAN** and **Currency**.
    """
)
st.sidebar.markdown("---")
st.sidebar.header("Output Details")
st.sidebar.markdown(
    """
    - **Naming Convention:** Files are named using the Currency and a portion of the IBAN (e.g., `AED-940.csv`).
    - **Download:** Downloads a `.zip` file containing separate `.csv` files for *each unique bank account*.
    """
)
st.sidebar.info("Tip: Ensure your PDFs are not password-protected.")


# --- MAIN PAGE CONTENT ---
st.title("WIO Statement Converter & Splitter 🚀")
st.caption("Now using native table extraction for stability across all WIO formats.")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

# --- CORE FUNCTION: EXTRACT TRANSACTIONS USING TABLE DETECTION ---
def extract_transactions(pdf_file):
    data = []
    VALID_CURRENCIES = ["AED", "USD", "EUR", "GBP"]
    current_account_key = None 
    IBAN_REGEX = r"(AE\s*\d{22})" 
    
    # Define table settings based on the WIO statement structure
    table_settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_vertical": [100, 180, 500, 600, 700], # Approximate X-coordinates for the major transaction columns (Date, Ref, Amount, Balance)
        "snap_horizontal": [80, 700], # Approximate Y-coordinates for header/footer (optional, but helps define the area)
        "intersection_y_tolerance": 5,
    }

    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()

            # STEP 1: ROBUST ACCOUNT KEY FINDER (IBAN + Currency)
            # This must run on every page to update the account key
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
            
            # Skip if we don't know the account yet (likely the first page summary)
            if not current_account_key:
                continue

            # STEP 2: TABLE EXTRACTION (The new, stable method)
            
            # The WIO statements use table lines, so we extract all tables
            tables = page.extract_tables(table_settings=table_settings)

            if not tables:
                continue

            # Process the table(s) found on the page
            for table in tables:
                # The first row is always the header, so skip it
                for row in table[1:]:
                    # Clean up data cells: remove newlines, commas, and excess spaces
                    cleaned_row = [cell.replace('\n', ' ').strip() if cell else '' for cell in row]
                    
                    # WIO tables usually have 5 or 6 primary columns: Date, Ref, Desc, Amount, Balance
                    # If the row is not long enough or starts with a non-date, skip it
                    if len(cleaned_row) < 5 or not re.match(r"\d{2}[/-]\d{2}[/-]\d{2,4}", cleaned_row[0]):
                        continue
                    
                    try:
                        date = cleaned_row[0]
                        reference = cleaned_row[1]
                        
                        # Description is usually the third column
                        description = cleaned_row[2]
                        
                        # Find the two numerical values (Amount and Balance). They might be columns 3 and 4, or 4 and 5 depending on layout.
                        # We use the known column positions for Amount and Balance from the WIO structure.
                        # Clean the number strings before conversion
                        amount_str = cleaned_row[-2].replace(',', '').strip()
                        balance_str = cleaned_row[-1].replace(',', '').strip()

                        amount = float(amount_str)
                        balance = float(balance_str)
                        
                        iban, currency = current_account_key.split('-')
                        
                        data.append([
                            date, reference, description, amount, balance, 
                            currency, iban 
                        ])
                    except (ValueError, IndexError):
                        # Skip if conversion fails (e.g., if column is a header repeated mid-page, or a line with text only)
                        continue
                        
    return data

if uploaded_file:
    try:
        data = extract_transactions(uploaded_file)
    except Exception as e:
        st.error(f"A critical error occurred during file processing: {e}. Please ensure the PDF is not corrupted.")
        st.stop()
        
    # -------------------------------------------
    # STEP 3: SMART DOWNLOAD LOGIC
    # -------------------------------------------
    
    if not data:
        st.error("❌ No transactions or account keys found in the PDF. The file structure may have changed or the tables could not be detected.")
        st.stop()
        
    df = pd.DataFrame(data, columns=["Date", "Reference", "Description", "Amount", "Balance", "Currency", "IBAN"])
    
    st.success(f"✅ Successfully processed {len(df)} transactions.")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("Data Preview")
        st.dataframe(df.drop(columns=['IBAN']), use_container_width=True)

    with col2:
        st.subheader("Download Files")
        unique_account_keys = df["IBAN"] + "-" + df["Currency"]
        
        def generate_csv_data(df_to_write):
            # Dropping the IBAN column here as it's not needed in the final CSV for accounting, but we can keep it if needed.
            return df_to_write.to_csv(index=False).encode('utf-8')

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for account_key in unique_account_keys.unique():
                iban, currency = account_key.split('-')
                subset_df = df[(df["IBAN"] == iban) & (df["Currency"] == currency)].copy()
                
                csv_data = generate_csv_data(subset_df)
                
                file_name = f"{currency}-{iban[-3:]}.csv"
                zf.writestr(file_name, csv_data)

            st.download_button(
                label=f"📦 Download All {len(unique_account_keys.unique())} Accounts (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="Wio_Statements_Split_by_Account.zip",
                mime="application/zip",
                key='multi_account_download'
            )
