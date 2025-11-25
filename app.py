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
    **Sequential Parsing Mode**
    
    This version separates accounts based on their **sequence** in the PDF file.
    
    - It detects a new account whenever it sees the **"ACCOUNT TYPE"** header.
    - Files are named by sequence and currency (e.g., `1_AED.csv`, `2_USD.csv`).
    """
)
st.sidebar.markdown("---")
st.sidebar.info("Tip: This solves issues where the IBAN could not be read. It simply treats the first account found as Account 1, the next as Account 2, etc.")

# --- MAIN PAGE CONTENT ---
st.title("WIO Statement Converter & Splitter 🔢")
st.caption("Sequential Account Parsing Mode")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

def extract_transactions(pdf_file):
    data = []
    VALID_CURRENCIES = ["AED", "USD", "EUR", "GBP"]
    
    # Sequence Trackers
    current_account_id = 0
    current_currency = "UNKNOWN"
    is_inside_account = False # Flag to know if we have started processing an account
    
    # Regex to find the start of a new account section
    # "ACCOUNT TYPE" appears at the top of the details page for each account
    NEW_ACCOUNT_MARKER = "ACCOUNT TYPE"

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            
            # --- STEP 1: DETECT NEW ACCOUNT START ---
            if NEW_ACCOUNT_MARKER in text:
                # We found a new account section!
                current_account_id += 1
                is_inside_account = True
                
                # Try to find the currency for this new account
                # Look for "Balance (XXX)" or "CURRENCY XXX"
                currency_match = re.search(r"Balance.*?(" + "|".join(VALID_CURRENCIES) + r")", text, re.IGNORECASE | re.DOTALL)
                
                if currency_match:
                    current_currency = currency_match.group(1).upper().strip()
                else:
                    # Fallback: Look for "USD Account", "AED Account" text
                    acc_name_match = re.search(r"\b(" + "|".join(VALID_CURRENCIES) + r")\s+Account\b", text, re.IGNORECASE)
                    if acc_name_match:
                        current_currency = acc_name_match.group(1).upper().strip()
            
            # If we haven't hit the first account yet (e.g. we are on the summary page), skip
            if not is_inside_account:
                continue

            # --- STEP 2: LINE-BY-LINE CSV PARSING ---
            lines = text.split('\n')
            
            for line in lines:
                line = line.strip()
                
                # PATTERN: Line starts with a quote, followed by a date
                # Example: "29/09/2025","P736..."
                if re.match(r'^"\d{2}[/-]\d{2}[/-]\d{2,4}"', line):
                    
                    # Extract fields
                    fields = re.findall(r'"(.*?)"', line)
                    fields = [f.strip().replace('\n', ' ') for f in fields]
                    
                    if len(fields) >= 4:
                        try:
                            date = fields[0]
                            reference = fields[1]
                            
                            # Amount and Balance are always the last two
                            balance_str = fields[-1].replace(',', '')
                            amount_str = fields[-2].replace(',', '')
                            
                            description = " ".join(fields[2:-2])
                            
                            amount = float(amount_str)
                            balance = float(balance_str)
                            
                            data.append([
                                date, reference, description, amount, balance, 
                                current_currency, current_account_id
                            ])
                            
                        except (ValueError, IndexError):
                            continue

    return data

if uploaded_file:
    try:
        with st.spinner("Scanning document sequence..."):
            data = extract_transactions(uploaded_file)
            
        if not data:
            st.error("❌ No transactions found. Please ensure the PDF contains 'ACCOUNT TYPE' headers and standard transaction lines.")
            st.stop()
            
        # Create DataFrame
        df = pd.DataFrame(data, columns=["Date", "Reference", "Description", "Amount", "Balance", "Currency", "AccountID"])
        
        st.success(f"✅ Extracted {len(df)} transactions from {len(df['AccountID'].unique())} sequential accounts.")
        
        # --- PREVIEW & DOWNLOAD ---
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("Preview")
            st.dataframe(df.drop(columns=['AccountID']), use_container_width=True)
            
        with col2:
            st.subheader("Download")
            
            def to_csv(d):
                return d.to_csv(index=False).encode('utf-8')
            
            # Group by AccountID (The Sequence Number)
            unique_ids = df['AccountID'].unique()
            unique_ids.sort()
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for acc_id in unique_ids:
                    # Filter data
                    subset = df[df['AccountID'] == acc_id]
                    
                    # Get currency for this chunk
                    curr = subset['Currency'].iloc[0]
                    
                    # File Name: [Sequence]_[Currency].csv -> e.g. "1_AED.csv"
                    fname = f"Account_{acc_id}_{curr}.csv"
                    
                    zf.writestr(fname, to_csv(subset))
            
            st.download_button(
                label="📦 Download All (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="Wio_Statements_Seq.zip",
                mime="application/zip"
            )

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
