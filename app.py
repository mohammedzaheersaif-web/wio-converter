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

# --- SIDEBAR ---
st.sidebar.title("⚙️ How to Use")
st.sidebar.markdown(
    """
    **Universal WIO Parser**
    
    This version bypasses table detection entirely. It scans the raw text for lines that look like CSV transaction rows.
    
    It separates accounts based on the unique **IBAN** found on the page.
    """
)
st.sidebar.markdown("---")
st.sidebar.info("Tip: This method is resilient to layout changes because it targets the specific text format of the transaction lines.")

# --- MAIN PAGE CONTENT ---
st.title("WIO Statement Converter & Splitter 💎")
st.caption("Universal Text-Row Parsing Mode")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

def extract_transactions(pdf_file):
    data = []
    VALID_CURRENCIES = ["AED", "USD", "EUR", "GBP"]
    
    # We maintain the current account info across pages
    current_iban = None
    current_currency = None
    
    # Regex to find IBAN (AE followed by digits)
    # Allowing flexible whitespace
    IBAN_REGEX = r"(AE\s*\d{22})"

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            
            # --- STEP 1: UPDATE CURRENT ACCOUNT INFO ---
            # Check if this page introduces a new IBAN/Account
            iban_match = re.search(IBAN_REGEX, text)
            currency_match = re.search(r"Balance.*?(" + "|".join(VALID_CURRENCIES) + r")", text, re.IGNORECASE | re.DOTALL)
            
            # If a new IBAN is found on this page, update our tracker
            if iban_match:
                current_iban = re.sub(r'\s+', '', iban_match.group(1)).strip()
            
            # If a currency header is found, update our tracker
            # (Sometimes currency is listed separately from IBAN)
            if currency_match:
                current_currency = currency_match.group(1).upper().strip()

            # If we haven't found an IBAN yet, we can't assign transactions
            if not current_iban:
                continue
            
            # Fallback for currency: if not found, assume AED or wait (optional)
            # But usually WIO has it. We will use "UNKNOWN" if missing but IBAN exists.
            row_currency = current_currency if current_currency else "UNKNOWN"

            # --- STEP 2: LINE-BY-LINE CSV PARSING ---
            # We split the text into lines and check if the line looks like a transaction
            lines = text.split('\n')
            
            for line in lines:
                line = line.strip()
                
                # PATTERN: Line starts with a quote, followed by a date, followed by a closing quote
                # Example: "29/09/2025","P736..."
                if re.match(r'^"\d{2}[/-]\d{2}[/-]\d{2,4}"', line):
                    
                    # This is a transaction row!
                    # Use Regex to extract all quoted fields: "content"
                    fields = re.findall(r'"(.*?)"', line)
                    
                    # Clean fields (remove internal newlines/spaces)
                    fields = [f.strip().replace('\n', ' ') for f in fields]
                    
                    # WIO CSV-lines usually have 5 columns: Date, Ref, Desc, Amount, Balance
                    # Sometimes Description is split, so we focus on the First 2 (Date, Ref) and Last 2 (Amount, Balance)
                    if len(fields) >= 4:
                        try:
                            date = fields[0]
                            reference = fields[1]
                            
                            # Amount and Balance are always the last two
                            balance_str = fields[-1].replace(',', '')
                            amount_str = fields[-2].replace(',', '')
                            
                            # Description is everything in between
                            description = " ".join(fields[2:-2])
                            
                            amount = float(amount_str)
                            balance = float(balance_str)
                            
                            data.append([
                                date, reference, description, amount, balance, 
                                row_currency, current_iban
                            ])
                            
                        except (ValueError, IndexError):
                            # If numbers fail to parse, skip this line (it might be a header line)
                            continue

    return data

if uploaded_file:
    try:
        with st.spinner("Scanning document for transaction lines..."):
            data = extract_transactions(uploaded_file)
            
        if not data:
            st.error("❌ No transactions found. Please ensure the PDF is a WIO statement containing transaction history.")
            st.stop()
            
        # Create DataFrame
        df = pd.DataFrame(data, columns=["Date", "Reference", "Description", "Amount", "Balance", "Currency", "IBAN"])
        
        st.success(f"✅ Extracted {len(df)} transactions from {len(df['IBAN'].unique())} unique account(s).")
        
        # --- PREVIEW & DOWNLOAD ---
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("Preview")
            # Show preview without IBAN column for cleanliness
            st.dataframe(df.drop(columns=['IBAN']), use_container_width=True)
            
        with col2:
            st.subheader("Download")
            
            # Helper to Convert DF to CSV bytes
            def to_csv(d):
                return d.to_csv(index=False).encode('utf-8')
            
            # Create unique keys for splitting (IBAN + Currency)
            unique_keys = df[['IBAN', 'Currency']].drop_duplicates().values
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for iban, currency in unique_keys:
                    # Filter data
                    subset = df[(df['IBAN'] == iban) & (df['Currency'] == currency)]
                    
                    # File Name: Currency-Last3DigitsIBAN.csv
                    fname = f"{currency}-{iban[-3:]}.csv"
                    
                    zf.writestr(fname, to_csv(subset))
            
            st.download_button(
                label="📦 Download All (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="Wio_Statements.zip",
                mime="application/zip"
            )

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
