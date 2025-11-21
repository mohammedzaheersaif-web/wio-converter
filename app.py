import streamlit as st
import pdfplumber
import pandas as pd
import io

st.title("WIO Bank PDF to CSV Converter")

uploaded_file = st.file_uploader("Upload WIO Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    data = []

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            
            lines = text.split("\n")
            for line in lines:
                parts = line.split()
                
                # Detect dates (WIO format: YYYY-MM-DD or DD-MM-YYYY)
                if len(parts) > 2 and "-" in parts[0]:
                    date = parts[0]
                    amount = parts[-1]

                    try:
                        amt = float(amount.replace(",", ""))
                    except:
                        continue

                    # Debit = negative
                    if amt < 0:
                        amt = -abs(amt)
                    else:
                        amt = abs(amt)

                    description = " ".join(parts[1:-1])

                    data.append([date, description, amt])

    df = pd.DataFrame(data, columns=["Date", "Description", "Amount"])

    st.write("### Extracted Transactions")
    st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download CSV",
        data=csv,
        file_name="wio_transactions.csv",
        mime="text/csv",
    )
