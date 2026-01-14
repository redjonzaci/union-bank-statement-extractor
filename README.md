# 🏦 Union Bank Statement Extractor

A simple web app to extract transactions from Union Bank PDF statements.

## How to Use

1. **Upload** your Union Bank PDF statement
2. **Download** the extracted CSV files:
   - `transactions.csv` - All transactions
   - `transactions_jo_veprim_ne_pos.csv` - Transactions without POS entries
   - `transactions.txt` - Raw extracted text

## Run Locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy to Streamlit Cloud

1. Fork this repository
2. Go to [Streamlit Cloud](https://streamlit.io/cloud)
3. Sign in with GitHub
4. Click "New app" and select this repo
5. Deploy!
