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
        # New key: Tracks the combination of IBAN and Currency (e.g., "AE123...-AED")
        current_account_key = None 

        # Regex to find an IBAN (starts with AE, followed by 22 digits)
        IBAN_REGEX = r"(AE\d{22})" 

        with pdfplumber.open(uploaded_file) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text()
                if not text:
                    continue

                # -------------------------------------------
                # STEP 1: ROBUST ACCOUNT KEY FINDER (IBAN + Currency)
                # -------------------------------------------
                
                # 1. Look for IBAN (must be done first, as it defines the account block)
                iban_match = re.search(IBAN_REGEX, text)
                
                # 2. Look for Currency in the transaction header (e.g., Balance (AED))
                currency_match = re.search(r"Balance.*?(" + "|".join(VALID_CURRENCIES) + r")", text, re.IGNORECASE | re.DOTALL)
                
                found_iban = None
                found_currency = None

                if iban_match:
                    found_iban = iban_match.group(1).strip()
                
                if currency_match:
                    found_currency = currency_match.group(1).upper().strip()

                # If we found both, create the new unique key
                if found_iban and found_currency:
                    # Update the key that persists for the following transactions
                    current_account_key = f"{found_iban}-{found_currency}"
                
                # IMPORTANT: If the statement is split across pages, the IBAN/Currency 
                # might not be on every single page header. We rely on the key 
                # from the previous detection if the current page has no header.

                # -------------------------------------------
                # STEP 2: EXTRACT TRANSACTIONS
                # -------------------------------------------
                lines = text.split("\n")
                
                for line in lines:
                    date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                    
                    # Only process if a date is found AND we know which account it belongs to
                    if date_match and current_account_key:
                        date = date_match.group(1)
                        rest_of_line = date_match.group(2).split()
                        numbers = [p.replace(",", "") for p in rest_of_line if re.match(r"-?\d+(\.\d+)?", p)]

                        if len(numbers) >= 2:
                            try:
                                balance = float(numbers[-1])
                                amount = float(numbers[-2])
                                
                                reference = rest_of_line[0]
                                description = " ".join(rest_of_line[1:-2])
                                
                                # Extract Currency and IBAN from the key for the final DataFrame
                                iban, currency = current_account_key.split('-')

                                data.append([
                                    date, reference, description, amount, balance, 
                                    currency, iban # Store both currency and IBAN
                                ])
                            except ValueError:
                                continue

        # -------------------------------------------
        # STEP 3: SMART DOWNLOAD LOGIC
        # -------------------------------------------
        df = pd.DataFrame(data, columns=["Date", "Reference", "Description", "Amount", "Balance", "Currency", "IBAN"])

        if not df.empty:
            st.success(f"✅ Successfully processed {len(df)} transactions.")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.subheader("Data Preview")
                st.dataframe(df, use_container_width=True)

            with col2:
                st.subheader("Download Files")
                # Group by the unique account identifier (IBAN-Currency)
                unique_account_keys = df["IBAN"] + "-" + df["Currency"]
                
                # Function to generate CSV data
                def generate_csv_data(df_to_write):
                    return df_to_write.to_csv(index=False).encode('utf-8')

                # All statements, even single-currency, now download as a ZIP for consistency
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for account_key in unique_account_keys.unique():
                        # Get the subset of transactions for this specific account
                        iban, currency = account_key.split('-')
                        subset_df = df[(df["IBAN"] == iban) & (df["Currency"] == currency)]
                        
                        csv_data = generate_csv_data(subset_df)
                        
                        # New File Naming: Currency-Last3DigitsOfIBAN.csv (e.g., AED-940.csv)
                        file_name = f"{currency}-{iban[-3:]}.csv"
                        zf.writestr(file_name, csv_data)

                st.download_button(
                    label=f"📦 Download All {len(unique_account_keys.unique())} Accounts (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="Wio_Statements_Split_by_Account.zip",
                    mime="application/zip",
                    key='multi_account_download'
                )
            
        else:
            st.error("❌ No transactions found. Please check the PDF for errors or ensure it contains transaction data.")
