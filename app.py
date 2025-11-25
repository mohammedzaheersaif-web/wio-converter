import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import zipfile

# -----------------------------------------------------------
#           PAGE CONFIG + VIBRANT WIO BRAND STYLING
# -----------------------------------------------------------
st.set_page_config(page_title="WIO Converter", layout="wide")

st.markdown("""
<style>

/* WIO Color Tokens */
:root {
    --wio-purple: #5C2D91;
    --wio-blue: #0099FF;
    --wio-teal: #00E0C6;
}

/* Fintech Gradient Header */
.title-container {
    background: linear-gradient(135deg, var(--wio-purple) 0%, var(--wio-teal) 100%);
    padding: 25px;
    border-radius: 18px;
    text-align: center;
    color: white !important;
    box-shadow: 0px 0px 20px rgba(92,45,145,0.25);
    margin-bottom: 25px;
}

/* How It Works card */
.side-box {
    background: rgba(0, 224, 198, 0.08);
    padding: 18px;
    border-radius: 14px;
    border: 2px solid rgba(0, 224, 198, 0.45);
    box-shadow: 0px 0px 10px rgba(0,224,198,0.15);
}

/* Upload box */
div[data-testid="stFileUploader"] {
    background-color: rgba(92,45,145,0.06);
    padding: 1.5rem;
    border-radius: 16px;
    border: 1px solid rgba(92,45,145,0.3);
    box-shadow: 0px 0px 10px rgba(92,45,145,0.10);
}

/* Tables & Data */
.dataframe {
    border-radius: 14px;
    overflow: hidden;
}

/* Primary Button Styling */
div.stDownloadButton > button, .stButton>button {
    background-color: var(--wio-purple);
    color: white !important;
    font-weight: 600;
    font-size: 16px;
    border-radius: 12px;
    padding: 10px 18px;
    border: none;
    transition: 0.25s;
    box-shadow: 0px 0px 12px rgba(92,45,145,0.25);
}

div.stDownloadButton > button:hover, .stButton>button:hover {
    background-color: var(--wio-blue);
    transform: scale(1.05);
    box-shadow: 0px 0px 18px rgba(0,224,198,0.45);
}

/* Metrics chips */
.metric-badge {
    display: inline-block;
    background-color: #EAF0FF;
    padding: 7px 12px;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 700;
    margin: 6px;
    color: var(--wio-purple);
}

/* Dark Mode Auto Support */
@media (prefers-color-scheme: dark) {
    .side-box {
        background: rgba(255,255,255,0.08);
    }
    div[data-testid="stFileUploader"] {
        background-color: rgba(255,255,255,0.06);
    }
    .metric-badge {
        background-color: var(--wio-blue);
        color: white !important;
    }
}

</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
#                       HEADER
# -----------------------------------------------------------
st.markdown("""
<div class="title-container">
    <h1 style="margin:0;">WIO Statement Converter 🔄</h1>
</div>
""", unsafe_allow_html=True)


# -----------------------------------------------------------
#             TWO-COLUMN PROFESSIONAL LAYOUT
# -----------------------------------------------------------
left, right = st.columns([1.6, 1])

right.markdown("""
<div class="side-box">
    <h3 style="margin-bottom:8px;">📌 How It Works</h3>
    <ul style="font-size:16px; line-height:1.5;">
        <li>Select your WIO bank PDF 📄</li>
        <li>We auto-detect each Currency 💱 & Account 🏦</li>
        <li>Parse every transaction accurately ⚙️</li>
        <li>Download clean CSV files ⬇️</li>
    </ul>
</div>
""", unsafe_allow_html=True)


# -----------------------------------------------------------
#            UPLOAD PANEL
# -----------------------------------------------------------
uploaded_file = left.file_uploader("📥 Upload WIO PDF Statement", type=["pdf"])


# -----------------------------------------------------------
#          ORIGINAL EXTRACTION LOGIC — UNTOUCHED
# -----------------------------------------------------------
if uploaded_file:
    data = []
    VALID_CURRENCIES = ["AED", "USD", "EUR", "GBP"]
    current_currency = None
    current_account_id = None

    IBAN = r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"
    ACCNO = r"(Account\s*(Number|No\.?)\s*[:\-]?\s*)(\d{6,20})"

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue

            m1 = re.search(IBAN, text)
            m2 = re.search(ACCNO, text, re.IGNORECASE)
            if m1: current_account_id = m1.group(0)
            elif m2: current_account_id = m2.group(3)

            c = re.search(r"(" + "|".join(VALID_CURRENCIES) + r")\s*Account",
                          text, re.IGNORECASE)
            if c: current_currency = c.group(1).upper()

            for line in text.split("\n"):
                m = re.match(r"(\d{2}[/-]\d{2}[/-]\d{4})\s+(.*)", line)
                if not m: continue
                date = m.group(1)
                parts = m.group(2).split()
                nums = [p.replace(",", "") for p in parts if re.match(r"-?\d+(\.\d+)?", p)]

                if len(nums) >= 2:
                    try:
                        bal = float(nums[-1])
                        amt = float(nums[-2])
                        ref = parts[0]
                        desc = " ".join(parts[1:-2])
                        data.append([
                            date, ref, desc, amt, bal,
                            current_currency or "UNKNOWN",
                            current_account_id or "UNKNOWN_ACCOUNT"
                        ])
                    except:
                        continue

    df = pd.DataFrame(data, columns=["Date","Reference","Description","Amount","Balance","Currency","Account"])

    if not df.empty:
        left.success(f"🌟 {len(df)} transactions extracted successfully!")

        left.markdown(
            f"""
            <span class='metric-badge'>💱 {", ".join(df["Currency"].unique())}</span>
            <span class='metric-badge'>🏦 {len(df["Account"].unique())} Accounts</span>
            """,
            unsafe_allow_html=True,
        )

        left.dataframe(df, use_container_width=True)

        uniq_acc = df["Account"].unique()
        uniq_cur = df["Currency"].unique()

        def csv(x): return x.to_csv(index=False).encode('utf-8')

        # Single account
        if len(uniq_acc) == 1:
            if len(uniq_cur) == 1:
                left.download_button("⬇️ Download CSV",
                    csv(df), f"{uniq_cur[0]}.csv", "text/csv")
            else:
                z = io.BytesIO()
                with zipfile.ZipFile(z, "w") as zf:
                    for c in uniq_cur:
                        zf.writestr(f"{c}.csv", csv(df[df["Currency"] == c]))
                left.download_button("⬇️ Download All",
                    z.getvalue(),"WIO.zip","application/zip")

        # Multiple Accounts
        else:
            z = io.BytesIO()
            with zipfile.ZipFile(z, "w") as zf:
                for a in uniq_acc:
                    for c in uniq_cur:
                        s = df[(df["Account"] == a) & (df["Currency"] == c)]
                        if not s.empty:
                            zf.writestr(f"{a}_{c}.csv", csv(s))
            left.download_button("⬇️ Download by Account",
                z.getvalue(),"WIO_By_Account.zip","application/zip")

    else:
        left.warning("⚠️ No transactions found. Please confirm PDF format.")
