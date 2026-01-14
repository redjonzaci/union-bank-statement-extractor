#!/usr/bin/env python3
"""
Union Bank Statement Extractor - Web App
Upload a PDF and get CSV files back.
"""

import re
import csv
import io
import streamlit as st
from PyPDF2 import PdfReader

HEADERS_TO_REMOVE = [
    "NXJERRJE LLOGARIE",
    "Dega UB",
    "NUMERI I KLIENTIT:",
    "KLIENTI:",
    "ADRESA:",
    "RRUGA ",
    "NJESIA BASHKEIAKE",
    "TIRANE",
    "PERIUDHA -",
    "DATA E FILLIMIT:",
    "DATA E MBARIMIT:",
    "DATA E PRINTIMIT:",
    "LLOGARIA:",
    "FAQE NR.",
    "DATA  TIPI I TRANSAKSIONIT",
    "PERSHKRIMI               REFERENCA",
    "UNION BANK",
    "PERIUDHA                 :",
    "BALANCA E FILLIMIT",
    "-llogar",
]

SEPARATOR_PATTERN = re.compile(r"^-{20,}$")
DATE_PATTERN = re.compile(r"^(\d{2}-[A-Z]{3}-\d{4})\s*$")
AMOUNT_PATTERN = re.compile(r"[\d,]+\.\d{2}")
FIELDNAMES = [
    "Detajet",
    "Referenca",
    "Nr i Kartes",
    "Data/Ora",
    "Terminali",
    "Debi",
    "Kredi",
    "Balanca",
]


def remove_headers(text: str) -> str:
    cleaned = []
    for line in text.split("\n"):
        if any(h in line for h in HEADERS_TO_REMOVE):
            continue
        if SEPARATOR_PATTERN.match(line.strip()):
            continue
        line = line.rstrip()
        if line:
            cleaned.append(line)
    return "\n".join(cleaned)


def extract_field(label: str, line: str) -> str:
    match = re.search(rf"{re.escape(label)}:\s+(.+)", line)
    return match.group(1).strip() if match else ""


def parse_amounts(line: str) -> dict:
    result = {"debi": "", "kredi": "", "balanca": ""}
    for match in AMOUNT_PATTERN.finditer(line):
        amt = match.group().replace(",", "")
        pos = match.start()
        if pos >= 100:
            result["balanca"] = amt
        elif pos >= 80:
            result["kredi"] = amt
        elif pos >= 60:
            result["debi"] = amt
    return result


def process_pdf(pdf_file) -> tuple:
    reader = PdfReader(pdf_file)

    # Extract text
    all_text = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            cleaned = remove_headers(text)
            if cleaned.strip():
                all_text.append(cleaned)

    combined = "\n".join(all_text)
    lines = combined.split("\n")

    # Parse transactions
    rows = []
    i = 0
    while i < len(lines) - 6:
        if not DATE_PATTERN.match(lines[i].strip()):
            i += 1
            continue

        detajet = extract_field("Detajet", lines[i + 2])
        if not detajet:
            i += 1
            continue

        amounts = parse_amounts(lines[i + 1])
        rows.append(
            {
                "Detajet": detajet,
                "Referenca": extract_field("Referenca", lines[i + 3]),
                "Nr i Kartes": extract_field("Nr i Kartes", lines[i + 4]),
                "Data/Ora": extract_field("Data/Ora", lines[i + 5]),
                "Terminali": extract_field("Terminali", lines[i + 6]),
                "Debi": amounts["debi"],
                "Kredi": amounts["kredi"],
                "Balanca": amounts["balanca"],
            }
        )
        i += 7

    return rows, combined


def rows_to_csv(rows: list) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=FIELDNAMES)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# Streamlit UI
st.set_page_config(page_title="Union Bank Statement Extractor", page_icon="🏦")
st.title("🏦 Union Bank Statement Extractor")
st.write("Upload a Union Bank PDF statement to extract transactions to CSV.")

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file:
    with st.spinner("Processing PDF..."):
        rows, text = process_pdf(uploaded_file)

    st.success(f"✅ Found {len(rows)} transactions!")

    # All transactions CSV
    csv_all = rows_to_csv(rows)
    st.download_button(
        label="📥 Download transactions.csv",
        data=csv_all,
        file_name="transactions.csv",
        mime="text/csv",
    )

    # Filtered CSV (no POS)
    filtered = [
        r for r in rows if "Veprim ne" not in r["Detajet"] or "POS" not in r["Detajet"]
    ]
    csv_filtered = rows_to_csv(filtered)
    st.download_button(
        label=f"📥 Download transactions_jo_veprim_ne_pos.csv ({len(filtered)} rows)",
        data=csv_filtered,
        file_name="transactions_jo_veprim_ne_pos.csv",
        mime="text/csv",
    )

    # Raw text
    st.download_button(
        label="📥 Download transactions.txt",
        data=text,
        file_name="transactions.txt",
        mime="text/plain",
    )

    # Preview
    st.subheader("Preview (first 10 rows)")
    st.dataframe(rows[:10])
