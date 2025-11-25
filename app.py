import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import zipfile

# Set page configuration
st.set_page_config(page_title="WIO Converter", layout="wide")
st.title("WIO Bank Statement Converter")

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

            # -------------------------------------------
            # STEP 0: DETECT ACCOUNT ID ON THIS PAGE
            # -------------------------------------------
            # Try IBAN first
            iban_match = re.search(IBAN_PATTERN, text)
            acct_match = re.search(ACCOUNT_NO_PATTERN, text, re.IGNORECASE)

            if iban_match:
                current_account_id = iban_match.group(0)
            elif acct_match:
                # Group 3 is the actual number part
                current_account_id = acct_match.group(3)

            # If still nothing ever found, we will later fallback to "UNKNOWN_ACCOUNT"

            # -------------------------------------------
            # STEP 1: ROBUST CURRENCY FINDER (Your logic)
            # -------------------------------------------
            found_currency = None

            balance_match = re.search(
                r"Balance.*?(" + "|".join(VALID_CURRENCIES) + r")",
                text,
                re.IGNORECASE | re.DOTALL,
            )
            account_match = re.search(
                r"\b(" + "|".join(VALID_CURRENCIES) + r")\s+Account\b",
                text,
                re.IGNORECASE,
            )
            currency_lbl_match = re.search(
                r"CURRENCY.*?(" + "|".join(VALID_CURRENCIES) + r")",
                text,
                re.IGNORECASE | re.DOTALL,
            )

            if balance_match:
                found_currency = balance_match.group(1).upper()
            elif account_match:
                found_currency = account_match.group(1).upper()
            elif currency_lbl_match:
                found_currency = currency_lbl_match.group(1).upper()

            if found_currency:
                current_currency = found_currency

            # -------------------------------------------
            # STEP 2: EXTRACT TRANSACTIONS (Your logic)
            # -------------------------------------------
            lines = text.split("\n")
            for line in lines:
                # Date detection
                date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)

                if date_match:
                    date = date_match.group(1)
                    rest_of_line = date_match.group(2).split()

                    # Clean and find numbers
                    numbers = [
                        p.replace(",", "")
                        for p in rest_of_line
                        if re.match(r"-?\d+(\.\d+)?", p)
                    ]

                    if len(numbers) >= 2:
                        try:
                            # Assign Amount and Balance (last two numbers)
                            balance = float(numbers[-1])
                            amount = float(numbers[-2])

                            reference = rest_of_line[0]
                            description = " ".join(rest_of_line[1:-2])
                            row_currency = current_currency if current_currency else "UNKNOWN"
                            row_account = current_account_id if current_account_id else "UNKNOWN_ACCOUNT"

                            data.append(
                                [date, reference, description, amount, balance, row_currency, row_account]
                            )
                        except ValueError:
                            continue

    # -------------------------------------------
    # STEP 3: SMART DOWNLOAD LOGIC (CSV + multi-account)
    # -------------------------------------------
    df = pd.DataFrame(
        data,
        columns=["Date", "Reference", "Description", "Amount", "Balance", "Currency", "Account"],
    )

    if not df.empty:
        st.success(f"Processed {len(df)} transactions.")
        st.dataframe(df)

        unique_accounts = df["Account"].unique()
        unique_currencies = df["Currency"].unique()

        # Function to generate CSV data
        def generate_csv_data(df_to_write: pd.DataFrame) -> bytes:
            return df_to_write.to_csv(index=False).encode("utf-8")

        # CASE 1: Only one account present in this statement
        if len(unique_accounts) == 1:
            # Preserve your original behavior by currency
            if len(unique_currencies) == 1:
                currency_name = unique_currencies[0]
                st.download_button(
                    label=f"Download {currency_name}.csv",
                    data=generate_csv_data(df),
                    file_name=f"{currency_name}.csv",
                    mime="text/csv",
                )
            else:
                # Multiple currencies, single account -> ZIP by currency
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

        # CASE 2: Multiple accounts in the same PDF
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

                        # Either flat naming:
                        filename = f"{acc}_{curr}.csv"
                        # Or folder-style: filename = f"{acc}/{curr}.csv"

                        zf.writestr(filename, csv_data)

            st.download_button(
                label="Download All Accounts (ZIP of CSVs)",
                data=zip_buffer.getvalue(),
                file_name="Wio_Statements_By_Account.zip",
                mime="application/zip",
            )

    else:
        st.warning("No transactions found. Please check the PDF.")
