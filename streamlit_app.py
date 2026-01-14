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
    "",
    "Detajet",
    "Perfituesi",
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
    result = {"prefix": "", "debi": "", "kredi": "", "balanca": ""}
    first_amount_pos = None
    for match in AMOUNT_PATTERN.finditer(line):
        amt = match.group().replace(",", "")
        pos = match.start()
        if first_amount_pos is None or pos < first_amount_pos:
            first_amount_pos = pos
        if pos >= 100:
            result["balanca"] = amt
        elif pos >= 80:
            result["kredi"] = amt
        elif pos >= 60:
            result["debi"] = amt
    # Extract text before the first amount
    if first_amount_pos is not None:
        result["prefix"] = line[:first_amount_pos].strip()
    else:
        result["prefix"] = line.strip()
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
    while i < len(lines) - 3:
        if not DATE_PATTERN.match(lines[i].strip()):
            i += 1
            continue

        detajet = extract_field("Detajet", lines[i + 2])
        if not detajet:
            i += 1
            continue

        amounts = parse_amounts(lines[i + 1])

        # Check if Perfituesi is present on the next line after Detajet
        offset = 3
        perfituesi = ""
        if i + offset < len(lines) and "Perfituesi:" in lines[i + offset]:
            perfituesi = extract_field("Perfituesi", lines[i + offset])
            offset += 1

        rows.append(
            {
                "": amounts["prefix"],
                "Detajet": detajet,
                "Perfituesi": perfituesi,
                "Referenca": (
                    extract_field("Referenca", lines[i + offset])
                    if i + offset < len(lines)
                    else ""
                ),
                "Nr i Kartes": (
                    extract_field("Nr i Kartes", lines[i + offset + 1])
                    if i + offset + 1 < len(lines)
                    else ""
                ),
                "Data/Ora": (
                    extract_field("Data/Ora", lines[i + offset + 2])
                    if i + offset + 2 < len(lines)
                    else ""
                ),
                "Terminali": (
                    extract_field("Terminali", lines[i + offset + 3])
                    if i + offset + 3 < len(lines)
                    else ""
                ),
                "Debi": amounts["debi"],
                "Kredi": amounts["kredi"],
                "Balanca": amounts["balanca"],
            }
        )
        i += offset + 4

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

# Initialize session state
if "processed_file" not in st.session_state:
    st.session_state.processed_file = None
    st.session_state.rows = None
    st.session_state.text = None

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file:
    # Only process if it's a new file
    if st.session_state.processed_file != uploaded_file.name:
        with st.spinner("Processing PDF..."):
            rows, text = process_pdf(uploaded_file)
            st.session_state.processed_file = uploaded_file.name
            st.session_state.rows = rows
            st.session_state.text = text
    else:
        rows = st.session_state.rows
        text = st.session_state.text

    st.success(f"✅ Found {len(rows)} transactions!")

    # All transactions CSV
    csv_all = rows_to_csv(rows)
    st.download_button(
        label="📥 Download transactions.csv",
        data=csv_all,
        file_name="transactions.csv",
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
