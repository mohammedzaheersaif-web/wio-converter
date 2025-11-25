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

/* WIO Dark Blue */
:root {
    --wio-blue-dark: #00205B;
    --wio-blue-light: #00A3E0;
}

/* Gradient Title Banner */
.title-container {
    background: linear-gradient(135deg, var(--wio-blue-dark) 0%, var(--wio-blue-light) 100%);
    padding: 20px;
    border-radius: 14px;
    text-align: center;
    color: white !important;
    margin-bottom: 22px;
}

/* Side Panel (How It Works) */
.side-box {
    background: rgba(0, 32, 91, 0.08);
    padding: 18px;
    border-radius: 12px;
    border: 1px solid rgba(0, 32, 91, 0.25);
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
    background-color: var(--wio-blue-dark);
    color: white;
    font-weight: 600;
    font-size: 16px;
    border-radius: 10px;
    padding: 10px 18px;
    border: none;
    transition: 0.25s;
}
div.stDownloadButton > button:hover, .stButton>button:hover {
    background-color: #00173F;
    transform: scale(1.04);
}

/* Metrics badges */
.metric-badge {
    display: inline-block;
    background-color: #D9E8FF;
    padding: 6px 12px;
    margin: 6px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    color: var(--wio-blue-dark);
}

/* Dark Mode */
@media (prefers-color-scheme: dark) {
    .side-box {
        background: rgba(255,255,255,0.05);
        border-color: rgba(255,255,255,0.15);
    }
    .metric-badge {
        background-color: var(--wio-blue-light);
        color: #00205B;
    }
}

</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
#                    HEADER SECTION (Updated)
# -----------------------------------------------------------
st.markdown("""
<div class="title-container">
    <h1 style="margin:0;">WIO Bank Statement Converter</h1>
</div>
""", unsafe_allow_html=True)


# -----------------------------------------------------------
#            TWO COLUMN MODERN LAYOUT
# -----------------------------------------------------------
left, right = st.columns([1.5, 1])

right.markdown("""
<div class="side-box">
    <h3 style="margin-bottom:8px;">📌 How It Works</h3>
    <ul style="font-size:15px; line-height:1.5;">
        <li>Upload your WIO bank PDF 📄</li>
        <li>App detects currency & account numbers automatically 🔍</li>
        <li>Extracts every transaction accurately ⚙️</li>
        <li>Downloads clean CSV files by Account + Currency ⬇️</li>
    </ul>
</div>
""", unsafe_allow_html=True)


# -----------------------------------------------------------
#                  FILE UPLOAD PANEL
# -----------------------------------------------------------
uploaded_file = left.file_uploader("📥 Upload WIO Bank Statement (PDF)", type=["pdf"])


# -----------------------------------------------------------
#            YOUR ORIGINAL WORKING EXTRACTION LOGIC
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
            if not text: continue

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

            for line in text.split("\n"):
                m = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                if not m:
                    continue
                date = m.group(1)
                parts = m.group(2).split()
                nums = [p.replace(",", "") for p in parts if re.match(r"-?\d+(\.\d+)?", p)]

                if len(nums) >= 2:
                    try:
                        balance = float(nums[-1])
                        amount = float(nums[-2])
                        ref = parts[0]
                        desc = " ".join(parts[1:-2])
                        data.append([
                            date, ref, desc, amount, balance,
                            current_currency or "UNKNOWN",
                            current_account_id or "UNKNOWN_ACCOUNT"
                        ])
                    except:
                        continue

    df = pd.DataFrame(data, columns=["Date","Reference","Description","Amount","Balance","Currency","Account"])

    if not df.empty:
        left.success(f"✨ Extracted {len(df)} transactions!")

        left.markdown(
            f"""
            <span class='metric-badge'>💱 {", ".join(df["Currency"].unique())}</span>
            <span class='metric-badge'>🏦 {len(df["Account"].unique())} Accounts</span>
            """,
            unsafe_allow_html=True,
        )

        left.dataframe(df, use_container_width=True)

        unique_acc = df["Account"].unique()
        unique_curr = df["Currency"].unique()

        def csv(x): return x.to_csv(index=False).encode('utf-8')

        if len(unique_acc) == 1:
            if len(unique_curr) == 1:
                left.download_button("⬇️ Download CSV",
                    csv(df), f"{unique_curr[0]}.csv", "text/csv")
            else:
                z = io.BytesIO()
                with zipfile.ZipFile(z, "w") as zf:
                    for c in unique_curr:
                        zf.writestr(f"{c}.csv", csv(df[df["Currency"] == c]))
                left.download_button("⬇️ Download ZIP",
                    z.getvalue(), "WIO_Statements.zip","application/zip")

        else:
            z = io.BytesIO()
            with zipfile.ZipFile(z, "w") as zf:
                for a in unique_acc:
                    for c in unique_curr:
                        sub = df[(df["Account"] == a) & (df["Currency"] == c)]
                        if not sub.empty:
                            zf.writestr(f"{a}_{c}.csv", csv(sub))
            left.download_button("⬇️ Download By Account (ZIP)",
                z.getvalue(),"WIO_By_Account.zip","application/zip")

    else:
        left.warning("⚠️ No transactions found. Check PDF.")
