import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import zipfile

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
    Upload your WIO Bank Statement PDF below. 
    The tool will automatically extract and separate transactions by their unique **IBAN** and **Currency**.
    """
)
st.sidebar.markdown("---")
st.sidebar.header("Output Details")
st.sidebar.markdown(
    """
    - **Naming Convention:** Files are named using the Currency and a portion of the IBAN (e.g., `AED-940.csv`).
    - **Multiple Files:** Downloads a `.zip` file containing separate `.csv` files for *each unique bank account*.
    """
)
st.sidebar.info("Tip: Ensure your PDFs are not password-protected.")


# --- MAIN PAGE CONTENT ---
st.title("WIO Statement Converter & Splitter 🔑")
st.caption("Now supports multiple accounts in the same currency (e.g., AED Account 1 & AED Account 2).")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    with st.spinner("Processing PDF and extracting data..."):
        data = []
        VALID_CURRENCIES = ["AED", "USD", "EUR", "GBP"]
        current_account_key = None 

        # Regex to find an IBAN, allowing spaces/newlines between AE and digits
        IBAN_REGEX = r"(AE\s*\d{22})" 

        with pdfplumber.open(uploaded_file) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text()
                if not text:
                    continue

                # -------------------------------------------
                # STEP 1: ROBUST ACCOUNT KEY FINDER (IBAN + Currency)
                # -------------------------------------------
                
                iban_match = re.search(IBAN_REGEX, text)
                currency_match = re.search(r"Balance.*?(" + "|".join(VALID_CURRENCIES) + r")", text, re.IGNORECASE | re.DOTALL)
                
                found_iban = None
                found_currency = None

                if iban_match:
                    # Clean the captured group to remove whitespace before storing
                    found_iban = re.sub(r'\s+', '', iban_match.group(1)).strip()
                
                if currency_match:
                    found_currency = currency_match.group(1).upper().strip()

                if found_iban and found_currency:
                    current_account_key = f"{found_iban}-{found_currency}"
                

                # -------------------------------------------
                # STEP 2: HYPER-ROBUST TRANSACTION EXTRACTION (Final attempt without adding new libraries)
                # -------------------------------------------
                lines = text.split("\n")
                
                for line in lines:
                    line = line.strip() # Crucial: Remove leading/trailing whitespace
                    
                    # Check if the line looks like a quoted, comma-separated transaction row: 
                    if line.startswith('"') and re.match(r'^"\d{2}[/-]\d{2}[/-]\d{4}"', line) and current_account_key:
                        
                        # Use re.findall to extract all fields enclosed in double quotes. 
                        # This should be highly stable for the WIO format.
                        fields = re.findall(r'"(.*?)"', line)
                        
                        # Check field count before proceeding
                        if len(fields) >= 5: 
                            date = fields[0]
                            reference = fields[1]
                            description = fields[2]
                            
                            balance_str = fields[-1].replace(',', '').strip()
                            amount_str = fields[-2].replace(',', '').strip()
                            
                            try:
                                balance = float(balance_str)
                                amount = float(amount_str)
                                
                                # Extract Currency and IBAN from the key
                                iban, currency = current_account_key.split('-')
                                
                                data.append([
                                    date, reference, description, amount, balance, 
                                    currency, iban 
                                ])
                            except ValueError:
                                # Skip lines where the amount/balance couldn't be converted to a number
                                continue

        # -------------------------------------------
        # STEP 3: SMART DOWNLOAD LOGIC
        # -------------------------------------------
        
        # Check if data is empty before creating the DataFrame to avoid the Key Error
        if not data:
            # We now rely solely on the explicit check to avoid the error
            st.error("❌ No transactions or account keys found in the PDF. The file structure may have changed. Please check the PDF.")
            return

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
