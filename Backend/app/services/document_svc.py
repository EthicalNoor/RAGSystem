import os
import shutil
import csv
import docx
import re
from PIL import Image
import fitz
import pytesseract
from fastapi import UploadFile, HTTPException
from typing import List
from app.repositories.sql_repo import SQLRepository
from app.config import Config, get_logger

logger = get_logger(__name__)

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
OCR_LANGUAGES = "eng+hin+mar+san"
MIN_TEXT_LENGTH_THRESHOLD = 150 

class DocumentService:
    def __init__(self, sql_repo: SQLRepository, config: Config):
        self.sql_repo = sql_repo
        self.config = config
        self.upload_dir = config.upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)

    async def save_upload(self, file: UploadFile):
        clean_name = file.filename.replace('\\', '/')
        safe_filename = clean_name.split('/')[-1]
        
        file_ext = safe_filename.split('.')[-1].upper() if '.' in safe_filename else "UNKNOWN"
        
        allowed_extensions = ["PDF", "DOCX", "TXT", "CSV"]
        if file_ext not in allowed_extensions:
            logger.warning(f"Rejected unsupported file: {safe_filename}")
            raise HTTPException(status_code=400, detail=f"Only {', '.join(allowed_extensions)} files are supported.")

        file_path = os.path.join(self.upload_dir, safe_filename)
        
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            
            doc_record = self.sql_repo.create_document(
                name=safe_filename,
                file_type=file_ext,
                size_mb=size_mb
            )
            logger.info(f"Saved file {safe_filename} to disk and database.")
            return doc_record
        except Exception as e:
            logger.error(f"Failed to save file {safe_filename}: {str(e)}")
            raise e

    def _is_text_corrupted(self, text: str) -> bool:
        if not text:
            return True
            
        mojibake_chars = set(
            "¡¢£¤¥¦§¨©ª«¬®¯°±²³´µ¶·¸¹º»¼½¾¿"
            "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß"
            "àáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýþÿ"
            "ﬂüœò˜—"
        )
        
        garbage_score = sum(1 for c in text if c in mojibake_chars)
        
        if (garbage_score / max(len(text), 1)) > 0.03:
            return True
            
        return False

    def _clean_extracted_text(self, text: str) -> str:
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.replace('||', '॥').replace('।।', '॥')
        text = text.replace(' | ', ' । ')
        text = re.sub(r'(?<=[a-zA-Z])-(?=[a-zA-Z])\n', '', text) 
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _semantic_chunk_text(self, text: str, max_chars: int, overlap_chars: int) -> List[dict]:
        separators = ["\n\n", "\n", ". ", " "]
        
        def split_recursively(text_to_split: str, current_separators: List[str]) -> List[str]:
            if len(text_to_split) <= max_chars:
                return [text_to_split]
                
            separator = current_separators[0]
            for sep in current_separators:
                if sep in text_to_split:
                    separator = sep
                    break
            else:
                return [text_to_split[i:i + max_chars] for i in range(0, len(text_to_split), max_chars - overlap_chars)]
                
            splits = text_to_split.split(separator)
            good_chunks = []
            current_chunk = ""
            
            for part in splits:
                part_len = len(part) + (len(separator) if current_chunk else 0)
                
                if len(part) > max_chars:
                    if current_chunk:
                        good_chunks.append(current_chunk.strip())
                        current_chunk = ""
                    next_seps = current_separators[1:] if len(current_separators) > 1 else current_separators
                    good_chunks.extend(split_recursively(part, next_seps))
                    continue
                    
                if len(current_chunk) + part_len <= max_chars:
                    current_chunk += (separator if current_chunk else "") + part
                else:
                    if current_chunk:
                        good_chunks.append(current_chunk.strip())
                        
                    overlap_text = current_chunk[-overlap_chars:] if overlap_chars > 0 else ""
                    if " " in overlap_text:
                        overlap_text = overlap_text.split(" ", 1)[-1]
                        
                    current_chunk = overlap_text + (separator if overlap_text else "") + part
                    
            if current_chunk:
                good_chunks.append(current_chunk.strip())
                
            return good_chunks

        raw_chunks = split_recursively(text, separators)
        
        final_chunks = []
        for c in raw_chunks:
            c = c.strip()
            if c:
                final_chunks.append({"text": c})
                
        return final_chunks

    def parse_and_chunk(self, document_id: str, chunk_size: int = 800) -> List[dict]:
        doc = self.sql_repo.get_document(document_id)
        if not doc:
            logger.warning(f"Cannot chunk unknown document {document_id}")
            return []

        file_path = os.path.join(self.upload_dir, doc.name)
        if not os.path.exists(file_path):
            logger.error(f"File not found on disk: {file_path}")
            return []

        logger.info(f"Parsing and chunking document {doc.name}")
        
        try:
            full_text = ""
            file_ext = doc.file_type
            
            if file_ext == "PDF":
                logger.info(f"Opening PDF with PyMuPDF: {doc.name}")
                pdf_doc = fitz.open(file_path)
                
                for page_num in range(len(pdf_doc)):
                    page = pdf_doc[page_num]
                    
                    native_text = page.get_text("text").strip()
                    page_text = ""
                    
                    if len(native_text) < MIN_TEXT_LENGTH_THRESHOLD or self._is_text_corrupted(native_text):
                        logger.info(f"Page {page_num + 1} failed quality check. Running Tesseract OCR ({OCR_LANGUAGES})...")
                        
                        pix = page.get_pixmap(dpi=300)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        
                        try:
                            page_text = pytesseract.image_to_string(img, lang=OCR_LANGUAGES).strip()
                        except Exception as ocr_err:
                            logger.error(f"OCR Failed on page {page_num + 1}: {ocr_err}")
                            page_text = native_text
                    else:
                        page_text = native_text
                    
                    full_text += page_text + "\n\n"
                
                pdf_doc.close()
                
            elif file_ext == "DOCX":
                doc_obj = docx.Document(file_path)
                full_text = "\n".join([para.text for para in doc_obj.paragraphs])
                
            elif file_ext == "TXT":
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    full_text = f.read()
                    
            elif file_ext == "CSV":
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        full_text += " | ".join(row) + "\n"
            else:
                logger.warning(f"Unsupported file extraction for {doc.name}")
                return []

            full_text = self._clean_extracted_text(full_text)

            if not full_text.strip():
                logger.warning(f"No parseable text found in {doc.name}.")
                return [{"text": f"[Empty or Image-Only Document: {doc.name}]"}]

            char_chunk_size = chunk_size * 4 
            overlap_chars = int((chunk_size * 0.125) * 4) 
            
            logger.info(f"Semantic Chunking initiated for {doc.name} (Max Chars: {char_chunk_size}, Overlap: {overlap_chars})")
            
            chunks = self._semantic_chunk_text(full_text, char_chunk_size, overlap_chars)

            logger.info(f"Generated {len(chunks)} semantic chunks for document {doc.name}")
            return chunks

        except Exception as e:
            logger.error(f"Error parsing document {doc.name}: {e}")
            raise e