import streamlit as st
import io
import os
import tempfile
import pdfplumber
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from datetime import datetime
import ocrmypdf

# --- Setup ---
st.set_page_config(page_title="Plating Sheets", layout="centered")
st.title("📄 Plating Sheets Combiner")

# --- Meal Code Input ---
meal_code_input = st.text_area(
    "Paste Meal Codes (one per line or comma separated):",
    height=200,
    placeholder="A2\nA3\nAV2\nAV3..."
)

st.markdown("""
    <style>
    textarea { resize: vertical; overflow-y: scroll; }
    </style>
""", unsafe_allow_html=True)

# --- Upload PDFs ---
uploaded_files = st.file_uploader(
    "Upload multi-page PDFs (Meal Code will be detected across all pages)",
    type="pdf",
    accept_multiple_files=True
)

# --- OCR Checkbox ---
use_ocr = st.checkbox("🧠 Convert uploaded PDFs to text-searchable (OCR)", value=False)

# --- Parse Meal Codes ---
def parse_meal_codes(text):
    lines = [line.strip().upper() for line in text.replace(",", "\n").splitlines()]
    return sorted([code for code in lines if code])

# --- OCR Conversion ---
def ocr_pdf(file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as input_tmp:
        input_tmp.write(file.read())
        input_path = input_tmp.name

    output_path = input_path.replace(".pdf", "_ocr.pdf")
    try:
        ocrmypdf.ocr(input_path, output_path, force_ocr=True, deskew=True)
        with open(output_path, "rb") as f:
            ocr_bytes = f.read()
        os.remove(input_path)
        os.remove(output_path)
        return io.BytesIO(ocr_bytes)
    except Exception as e:
        st.error(f"OCR failed: {e}")
        return None

# --- Meal Code Detection ---
def contains_meal_code(pdf_file, code):
    code = code.strip().upper()
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                words = text.replace("\n", " ").split()
                if code in words:
                    return True
    return False

# --- Match and Merge ---
def match_and_merge(files, codes):
    file_map = {}
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(codes)

    for i, code in enumerate(codes):
        found = False
        for file in files:
            if file not in file_map.values() and contains_meal_code(file, code):
                file_map[code] = file
                found = True
                break
        if not found:
            st.warning(f"Meal Code '{code}' not found in any uploaded files.")

        progress = (i + 1) / total
        progress_bar.progress(progress)
        status_text.text(f"Processing {i + 1} of {total} Meal Codes...")

    merger = PdfMerger()
    for code in codes:
        if code in file_map:
            pdf_reader = PdfReader(file_map[code])
            merger.append(pdf_reader)

    output = io.BytesIO()
    merger.write(output)
    merger.close()
    output.seek(0)
    status_text.text("✅ Finished combining!")
    progress_bar.empty()
    return output

# --- Flatten Final PDF ---
def flatten_pdf(input_pdf):
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    output_io = io.BytesIO()
    writer.write(output_io)
    output_io.seek(0)
    return output_io

# --- Process Flow ---
if uploaded_files and meal_code_input:
    meal_codes = parse_meal_codes(meal_code_input)

    processed_files = []
    for file in uploaded_files:
        if use_ocr:
            st.info(f"OCR processing: {file.name}")
            ocr_file = ocr_pdf(file)
            if ocr_file:
                ocr_file.name = file.name
                processed_files.append(ocr_file)
        else:
            processed_files.append(file)

    if st.button("🔀 Combine & Flatten PDF"):
        merged_pdf = match_and_merge(processed_files, meal_codes)
        final_pdf = flatten_pdf(merged_pdf)

        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"Plating_Sheets_{today}.pdf"

        st.success("✅ PDF created and flattened for printing!")
        st.download_button("📥 Download PDF", final_pdf, filename, mime="application/pdf")
