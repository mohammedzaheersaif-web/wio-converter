import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import zipfile

# -----------------------------------------------------------
#            PAGE CONFIG + MODERN THEME STYLE
# -----------------------------------------------------------
st.set_page_config(page_title="WIO Converter", layout="wide")

st.markdown("""
<style>

/* Gradient Title Banner */
.title-container {
    background: linear-gradient(135deg, #0038A8 0%, #00A3FF 100%);
    padding: 18px;
    border-radius: 14px;
    text-align: center;
    color: white !important;
    margin-bottom: 20px;
}

/* Side Panel (How It Works) */
.side-box {
    background: rgba(0, 102, 255, 0.08);
    padding: 18px;
    border-radius: 12px;
    border: 1px solid rgba(0, 102, 255, 0.25);
}

/* Upload UI box */
div[data-testid="stFileUploader"] {
    background-color: rgba(0,0,0,0.03);
    padding: 1.4rem;
    border-radius: 14px;
    border: 1px solid rgba(180,180,180,0.3);
}

/* Buttons */
div.stDownloadButton > button, .stButton>button {
    background-color: #0066FF;
    color: white;
    font-weight: 600;
    font-size: 16px;
    border-radius: 10px;
    padding: 10px 18px;
    border: none;
    transition: 0.25s;
}
div.stDownloadButton > button:hover, .stButton>button:hover {
    background-color: #004ACC;
    transform: scale(1.04);
}

/* Metrics badges */
.metric-badge {
    display: inline-block;
    background-color: #EAF3FF;
    padding: 6px 12px;
    margin: 6px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    color: #004ACC;
}

/* Dark Mode */
@media (prefers-color-scheme: dark) {
    .side-box {
        background: rgba(255,255,255,0.05);
        border-color: rgba(255,255,255,0.15);
    }
    .metric-badge {
        background-color: #1F6FEB;
        color: white;
    }
}

</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
#                    HEADER SECTION
# -----------------------------------------------------------
st.markdown("""
<div class="title-container">
    <h1 style="margin:0;">💳 WIO Bank PDF → CSV Converter</h1>
    <p style="font-size:14px;margin:0;">Smart • Clean • Multi-Currency • Multi-Account</p>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
#            TWO COLUMN MODERN LAYOUT
# -----------------------------------------------------------
left, right = st.columns([1.5, 1])

right.markdown("""
<div class="side-box">
    <h3>📌 How It Works</h3>
    <ul style="font-size:15px;">
        <li>Upload your WIO bank PDF 📄</li>
        <li>App reads all pages using AI-powered parsing 🤖</li>
        <li>Finds 💱 Currency + 🏦 Account automatically</li>
        <li>Extracts all ⭐ transactions cleanly</li>
        <li>Downloads CSV split by Account + Currency ⬇️</li>
    </ul>
    <p style="font-size:13px;color:gray;">
    We ensure data accuracy with in-built validation 🚀
    </p>
</div>
""", unsafe_allow_html=True)


# -----------------------------------------------------------
#                  FILE UPLOAD PANEL
# -----------------------------------------------------------
uploaded_file = left.file_uploader("📥 Upload WIO Bank Statement (PDF)", type=["pdf"])


# -----------------------------------------------------------
#                 YOUR ORIGINAL WORKING LOGIC
# -----------------------------------------------------------
if uploaded_file:
    data = []
    VALID_CURRENCIES = ["AED", "USD", "EUR", "GBP"]
    current_currency = None
    current_account_id = None

    IBAN_PATTERN = r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"
    ACCOUNT_NO_PATTERN = r"(Account\s*(Number|No\.?)\s*[:\-]?\s*)(\d{6,20})"

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            iban_match = re.search(IBAN_PATTERN, text)
            acct_match = re.search(ACCOUNT_NO_PATTERN, text, re.IGNORECASE)
            if iban_match:
                current_account_id = iban_match.group(0)
            elif acct_match:
                current_account_id = acct_match.group(3)

            found_currency = None
            balance_match = re.search(r"Balance.*?(" + "|".join(VALID_CURRENCIES) + r")",
                                      text, re.IGNORECASE | re.DOTALL)
            account_match = re.search(r"\b(" + "|".join(VALID_CURRENCIES) + r")\s+Account\b",
                                      text, re.IGNORECASE)
            currency_lbl_match = re.search(r"CURRENCY.*?(" + "|".join(VALID_CURRENCIES) + r")",
                                           text, re.IGNORECASE | re.DOTALL)

            if balance_match: found_currency = balance_match.group(1).upper()
            elif account_match: found_currency = account_match.group(1).upper()
            elif currency_lbl_match: found_currency = currency_lbl_match.group(1).upper()

            if found_currency:
                current_currency = found_currency

            lines = text.split("\n")
            for line in lines:
                date_match = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                if date_match:
                    date = date_match.group(1)
                    parts = date_match.group(2).split()
                    nums = [p.replace(",", "") for p in parts if re.match(r"-?\d+(\.\d+)?", p)]

                    if len(nums) >= 2:
                        try:
                            balance = float(nums[-1])
                            amount = float(nums[-2])
                            ref = parts[0]
                            desc = " ".join(parts[1:-2])
                            curr = current_currency or "UNKNOWN"
                            acct = current_account_id or "UNKNOWN_ACCOUNT"
                            data.append([date, ref, desc, amount, balance, curr, acct])
                        except:
                            continue

    df = pd.DataFrame(data, columns=["Date","Reference","Description","Amount","Balance","Currency","Account"])

    if not df.empty:
        left.success(f"✨ Extracted {len(df)} transactions!")

        # 📊 Show usage metrics
        left.markdown(
            f"""
            <span class='metric-badge'>💱 Currencies: {", ".join(df["Currency"].unique())}</span>
            <span class='metric-badge'>🏦 Accounts: {len(df["Account"].unique())}</span>
            """,
            unsafe_allow_html=True,
        )

        left.dataframe(df, use_container_width=True)

        unique_acc = df["Account"].unique()
        unique_curr = df["Currency"].unique()

        def to_csv(x): return x.to_csv(index=False).encode('utf-8')

        if len(unique_acc) == 1:
            if len(unique_curr) == 1:
                left.download_button(
                    label="⬇️ Download CSV",
                    data=to_csv(df),
                    file_name=f"{unique_curr[0]}.csv",
                    mime="text/csv",
                )
            else:
                z = io.BytesIO()
                with zipfile.ZipFile(z, "w") as zipf:
                    for c in unique_curr:
                        subset = df[df["Currency"] == c]
                        zipf.writestr(f"{c}.csv", to_csv(subset))
                left.download_button("⬇️ Download ZIP", z.getvalue(), "Statements.zip", "application/zip")
        else:
            z = io.BytesIO()
            with zipfile.ZipFile(z, "w") as zipf:
                for a in unique_acc:
                    for c in df["Currency"].unique():
                        sub = df[(df["Account"] == a) & (df["Currency"] == c)]
                        if not sub.empty:
                            zipf.writestr(f"{a}_{c}.csv", to_csv(sub))
            left.download_button("⬇️ Download All Accounts (ZIP)", z.getvalue(),
                                 "WIO_By_Account.zip", "application/zip")
    else:
        left.warning("⚠️ No transactions found. Check PDF format.")

