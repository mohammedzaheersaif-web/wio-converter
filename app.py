import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import zipfile

# Page Configuration
st.set_page_config(page_title="WIO Converter", layout="wide")

# -----------------------✨ MODERN UI ✨------------------------
st.markdown("""
<style>

/* Center the main title */
h1 {
    text-align: center;
    font-size: 34px !important;
    font-weight: 700 !important;
    margin-bottom: 0.3em !important;
}

/* Subtle subtitle styling */
.app-subtitle {
    text-align:center;
    color:gray;
    font-size:15px;
    margin-top:-10px;
    margin-bottom:25px;
}

/* Main container spacing */
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
}

/* Upload box styling */
div[data-testid="stFileUploader"] {
    background-color: rgba(240,240,240,0.15);
    padding: 1.3rem;
    border-radius: 12px;
    border: 1px solid rgba(180,180,180,0.3);
    backdrop-filter: blur(10px);
    margin-bottom: 25px;
}

/* Table rounded corners */
.dataframe {
    border-radius: 12px;
    overflow: hidden;
}

/* Download + Action Buttons */
div.stDownloadButton > button, .stButton>button {
    background-color: #0066FF;
    color: white;
    border-radius: 10px;
    padding: 0.7rem 1.25rem;
    font-weight: 600;
    border: none;
    transition: 0.25s;
    font-size: 15px;
}

div.stDownloadButton > button:hover, .stButton>button:hover {
    background-color: #004ACC;
    transform: scale(1.04);
}

/* Light & Dark Auto Support */
@media (prefers-color-scheme: dark) {
    div[data-testid="stFileUploader"] {
        background-color: rgba(255,255,255,0.08);
        border-color: rgba(255,255,255,0.15);
    }
    .stButton>button, .stDownloadButton>button {
        background-color: #1F6FEB;
    }
}

</style>
""", unsafe_allow_html=True)
# -------------------------------------------------------------

st.title("WIO Bank Statement Converter")
st.markdown("<p class='app-subtitle'>Convert your WIO bank PDF into currency-split CSV files</p>",
            unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    data = []
    VALID_CURRENCIES = ["AED", "USD", "EUR", "GBP"]
    current_currency = None
    current_account_id = None  # Track which account this page belongs to

    # Patterns to detect account identifiers
    IBAN_PATTERN = r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"
    ACCOUNT_NO_PATTERN = r"(Account\s*(Number|No\.?)\s*[:\-]?\s*)(\d{6,20})"

    with pdfplumber.open(uploaded_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue

            # ACCOUNT DETECTION
            iban_match = re.search(IBAN_PATTERN, text)
            acct_match = re.search(ACCOUNT_NO_PATTERN, text, re.IGNORECASE)

            if iban_match:
                current_account_id = iban_match.group(0)
            elif acct_match:
                current_account_id = acct_match.group(3)

            # CURRENCY DETECTION
            found_currency = None
            balance_match = re.search(r"Balance.*?(" + "|".join(VALID_CURRENCIES) + r")",
                                      text, re.IGNORECASE | re.DOTALL)
            account_match = re.search(r"\b(" + "|".join(VALID_CURRENCIES) + r")\s+Account\b",
                                      text, re.IGNORECASE)
            currency_lbl_match = re.search(r"CURRENCY.*?(" + "|".join(VALID_CURRENCIES) + r")",
                                           text, re.IGNORECASE | re.DOTALL)

            if balance_match:
                found_currency = balance_match.group(1).upper()
            elif account_match:
                found_currency = account_match.group(1).upper()
            elif currency_lbl_match:
                found_currency = currency_lbl_match.group(1).upper()

            if found_currency:
                current_currency = found_currency

            # TRANSACTION EXTRACTION
            lines = text.split("\n")
            for line in lines:
                date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)

                if date_match:
                    date = date_match.group(1)
                    rest_of_line = date_match.group(2).split()

                    numbers = [p.replace(",", "") for p in rest_of_line
                               if re.match(r"-?\d+(\.\d+)?", p)]

                    if len(numbers) >= 2:
                        try:
                            balance = float(numbers[-1])
                            amount = float(numbers[-2])
                            reference = rest_of_line[0]
                            description = " ".join(rest_of_line[1:-2])
                            row_currency = current_currency if current_currency else "UNKNOWN"
                            row_account = current_account_id if current_account_id else "UNKNOWN_ACCOUNT"

                            data.append([date, reference, description,
                                         amount, balance, row_currency, row_account])
                        except ValueError:
                            continue

    # OUTPUT RESULTS
    df = pd.DataFrame(data, columns=["Date", "Reference", "Description",
                                     "Amount", "Balance", "Currency", "Account"])

    if not df.empty:
        st.success(f"Processed {len(df)} transactions.")
        st.dataframe(df, use_container_width=True)

        unique_accounts = df["Account"].unique()
        unique_currencies = df["Currency"].unique()

        def generate_csv_data(df_to_write):
            return df_to_write.to_csv(index=False).encode("utf-8")

        if len(unique_accounts) == 1:
            if len(unique_currencies) == 1:
                currency_name = unique_currencies[0]
                st.download_button(
                    label=f"Download {currency_name}.csv",
                    data=generate_csv_data(df),
                    file_name=f"{currency_name}.csv",
                    mime="text/csv",
                )
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for curr in unique_currencies:
                        subset_df = df[df["Currency"] == curr]
                        csv_data = generate_csv_data(subset_df)
                        zf.writestr(f"{curr}.csv", csv_data)

                st.download_button(
                    label="Download All (ZIP of CSVs)",
                    data=zip_buffer.getvalue(),
                    file_name="Wio_Statements.zip",
                    mime="application/zip",
                )

        else:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for acc in unique_accounts:
                    acc_df = df[df["Account"] == acc]
                    acc_currencies = acc_df["Currency"].unique()

                    for curr in acc_currencies:
                        subset_df = acc_df[acc_df["Currency"] == curr]
                        if subset_df.empty:
                            continue
                        csv_data = generate_csv_data(subset_df)
                        filename = f"{acc}_{curr}.csv"
                        zf.writestr(filename, csv_data)

            st.download_button(
                label="Download All Accounts (ZIP of CSVs)",
                data=zip_buffer.getvalue(),
                file_name="Wio_Statements_By_Account.zip",
                mime="application/zip",
            )
    else:
        st.warning("No transactions found. Please check the PDF.")
