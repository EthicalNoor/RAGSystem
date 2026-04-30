import os
import re
import json
import logging
import multiprocessing
from PIL import Image, ImageEnhance, ImageFilter
import fitz  # PyMuPDF
import pytesseract
from tqdm import tqdm

# ==========================================
# CONFIGURATION
# ==========================================
# Configure Tesseract path (Update if needed)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
OCR_LANGUAGES = "eng+hin+mar+san"
TESSERACT_CONFIG = r'--oem 3 --psm 3' 

PDF_FOLDER = r"E:\Ethical\RagSystem\pdf"
OUTPUT_JSON = "extracted_vedic_data.json"

MIN_TEXT_LENGTH_THRESHOLD = 50
MOJIBAKE_TOLERANCE = 0.05 

# ==========================================
# TEXT VALIDATION & CLEANING
# ==========================================
def is_text_corrupted(text: str) -> bool:
    """
    Intelligently detects if text is Mojibake (legacy non-Unicode fonts).
    FIXED: Removed standard English/Latin letters to prevent false positives.
    """
    if not text or len(text.strip()) < 10:
        return True

    # Purely legacy/garbage symbols that appear when Sanskrit fonts break.
    # No standard alphabets (v,w,x,y,z) are in this list anymore.
    mojibake_chars = set('ÊÃ¢ﬂH§üœò˜—™£¢∞§¶•ªºæø¿¡¬√ƒ≈∆«»…ÀÃÕŒœ–÷ÿŸ')
    
    garbage_count = sum(1 for c in text if c in mojibake_chars)
    text_length_no_spaces = len(text.replace(" ", "").replace("\n", ""))
    
    if text_length_no_spaces == 0:
        return True
        
    garbage_ratio = garbage_count / text_length_no_spaces
    return garbage_ratio > MOJIBAKE_TOLERANCE

def clean_extracted_text(text: str) -> str:
    """Normalizes spaces, fixes broken dandas, and removes excessive newlines."""
    text = text.replace('||', '॥').replace('।।', '॥')
    text = text.replace('|', '।')
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = '\n'.join([line.strip() for line in text.split('\n')])
    return text.strip()

# ==========================================
# EXTRACTION STRATEGIES
# ==========================================
def extract_ocr_text(page) -> str:
    """Applies image enhancement before passing to Tesseract."""
    try:
        pix = page.get_pixmap(dpi=300, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img = img.convert('L')
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        img = img.filter(ImageFilter.SHARPEN)

        text = pytesseract.image_to_string(img, lang=OCR_LANGUAGES, config=TESSERACT_CONFIG)
        return text
    except Exception as e:
        return ""

# ==========================================
# INTELLIGENT CHUNKING
# ==========================================
def chunk_page_content(text: str, page_num: int) -> list:
    """Chunks text into shlokas and commentary."""
    chunks = []
    text = clean_extracted_text(text)
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

    current_shloka = []
    current_explanation = []
    shloka_pattern = re.compile(r'[।॥](?:\s*[\d०-९\.\-]+\s*[।॥])?')

    for para in paragraphs:
        if shloka_pattern.search(para):
            if current_explanation and current_shloka:
                chunks.append({
                    "shloka": "\n".join(current_shloka),
                    "explanation": "\n".join(current_explanation),
                    "page": page_num,
                    "type": "verse_with_commentary"
                })
                current_shloka = []
                current_explanation = []
            current_shloka.append(para)
        else:
            if not current_shloka:
                chunks.append({"text": para, "page": page_num, "type": "general_text"})
            else:
                current_explanation.append(para)

    if current_shloka or current_explanation:
        chunks.append({
            "shloka": "\n".join(current_shloka) if current_shloka else None,
            "explanation": "\n".join(current_explanation) if current_explanation else None,
            "page": page_num,
            "type": "verse_with_commentary" if current_shloka else "general_text"
        })

    return chunks

# ==========================================
# PAGE-LEVEL PROCESSOR
# ==========================================
def process_pdf(pdf_path: str) -> tuple:
    """Processes a single PDF with real-time console updates."""
    file_name = os.path.basename(pdf_path)
    file_chunks = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        print(f"\n[STARTED] {file_name} ({total_pages} pages)")

        for page_num in range(total_pages):
            # Print an update to the console every 50 pages so you know it's not stuck
            if page_num > 0 and page_num % 50 == 0:
                print(f"   -> [{file_name}] Processed {page_num}/{total_pages} pages...")

            page = doc[page_num]
            final_text = page.get_text("text").strip()

            if len(final_text) < MIN_TEXT_LENGTH_THRESHOLD or is_text_corrupted(final_text):
                # Only OCR if absolutely necessary
                final_text = extract_ocr_text(page)

            if final_text.strip():
                chunks = chunk_page_content(final_text, page_num + 1)
                file_chunks.extend(chunks)

        doc.close()
        print(f"[FINISHED] {file_name} completed successfully.")
        return file_name, file_chunks

    except Exception as e:
        print(f"[ERROR] Failed processing {file_name}: {e}")
        return file_name, []

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == '__main__':
    if not os.path.exists(PDF_FOLDER):
        print(f"❌ ERROR: Folder '{PDF_FOLDER}' not found.")
        exit(1)

    pdf_files = [os.path.join(PDF_FOLDER, f) for f in os.listdir(PDF_FOLDER) if f.lower().endswith(".pdf")]

    print(f"📄 Found {len(pdf_files)} PDFs. Initiating extraction pipeline...\n")

    num_cores = max(1, multiprocessing.cpu_count() - 2)
    print(f"⚙️ Using {num_cores} parallel workers. Check the console for live updates!\n")

    final_output = {}

    with multiprocessing.Pool(num_cores) as pool:
        # Removed tqdm for map-reduce to allow our custom console prints to show cleanly
        results = pool.map(process_pdf, pdf_files)

    for file_name, chunks in results:
        if chunks:
            final_output[file_name] = chunks

    print("\n💾 Saving structured JSON...")
    
    try:
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(final_output, f, ensure_ascii=False, indent=4)
        print(f"✅ Extraction Complete! Data safely written to {OUTPUT_JSON}.")
    except Exception as e:
        print(f"❌ ERROR: Failed to write JSON output: {e}")