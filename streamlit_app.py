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

SEPARATOR_PATTERN = re.compile(r"^-[-\s]{19,}$")
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
    while i < len(lines) - 2:
        if not DATE_PATTERN.match(lines[i].strip()):
            i += 1
            continue

        amounts = parse_amounts(lines[i + 1])
        if not amounts["balanca"]:
            i += 1
            continue

        # Check for Detajet on line i+2 (single-line) or i+3 (multi-line description)
        # Also handle OCR typo "Detaj et:"
        detajet_offset = None
        detajet = ""
        for offset in [2, 3]:
            if i + offset < len(lines):
                line = lines[i + offset]
                if "Detajet:" in line or "Detaj et:" in line:
                    detajet = extract_field("Detajet", line) or extract_field(
                        "Detaj et", line
                    )
                    detajet_offset = offset
                    break

        # Handle transactions without Detajet (e.g., "Komisione te tjera ne llogari")
        if not detajet:
            # Skip to next date
            j = i + 2
            while j < len(lines) and not DATE_PATTERN.match(lines[j].strip()):
                j += 1
            rows.append(
                {
                    "": amounts["prefix"],
                    "Detajet": "",
                    "Perfituesi": "",
                    "Referenca": "",
                    "Nr i Kartes": "",
                    "Data/Ora": "",
                    "Terminali": "",
                    "Debi": amounts["debi"],
                    "Kredi": amounts["kredi"],
                    "Balanca": amounts["balanca"],
                }
            )
            i = j
            continue

        # Check the line after Detajet
        next_line_idx = i + detajet_offset + 1
        perfituesi = ""

        if next_line_idx < len(lines):
            next_line = lines[next_line_idx]

            # Case 1: Perfituesi or "Me Urdher Te" present
            if "Perfituesi:" in next_line or "Me Urdher Te:" in next_line:
                perfituesi_parts = [
                    extract_field("Perfituesi", next_line)
                    or extract_field("Me Urdher Te", next_line)
                ]
                # Collect continuation lines until we hit a date
                j = next_line_idx + 1
                while j < len(lines) and not DATE_PATTERN.match(lines[j].strip()):
                    perfituesi_parts.append(lines[j].strip())
                    j += 1
                perfituesi = " ".join(perfituesi_parts)
                rows.append(
                    {
                        "": amounts["prefix"],
                        "Detajet": detajet,
                        "Perfituesi": perfituesi,
                        "Referenca": "",
                        "Nr i Kartes": "",
                        "Data/Ora": "",
                        "Terminali": "",
                        "Debi": amounts["debi"],
                        "Kredi": amounts["kredi"],
                        "Balanca": amounts["balanca"],
                    }
                )
                i = j
                continue

            # Case 2: Next line is already a new date (transaction only had Detajet)
            if DATE_PATTERN.match(next_line.strip()):
                rows.append(
                    {
                        "": amounts["prefix"],
                        "Detajet": detajet,
                        "Perfituesi": "",
                        "Referenca": "",
                        "Nr i Kartes": "",
                        "Data/Ora": "",
                        "Terminali": "",
                        "Debi": amounts["debi"],
                        "Kredi": amounts["kredi"],
                        "Balanca": amounts["balanca"],
                    }
                )
                i = next_line_idx
                continue

        # Case 3: Standard POS transaction with Referenca, Nr i Kartes, etc.
        ref_line = i + detajet_offset + 1
        terminali = ""
        if ref_line + 3 < len(lines):
            term_line = lines[ref_line + 3]
            terminali = extract_field("Terminali", term_line) or extract_field(
                "Termi nali", term_line
            )

        rows.append(
            {
                "": amounts["prefix"],
                "Detajet": detajet,
                "Perfituesi": "",
                "Referenca": (
                    extract_field("Referenca", lines[ref_line])
                    if ref_line < len(lines)
                    else ""
                ),
                "Nr i Kartes": (
                    extract_field("Nr i Kartes", lines[ref_line + 1])
                    if ref_line + 1 < len(lines)
                    else ""
                ),
                "Data/Ora": (
                    extract_field("Data/Ora", lines[ref_line + 2])
                    if ref_line + 2 < len(lines)
                    else ""
                ),
                "Terminali": terminali,
                "Debi": amounts["debi"],
                "Kredi": amounts["kredi"],
                "Balanca": amounts["balanca"],
            }
        )
        i += detajet_offset + 5

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
