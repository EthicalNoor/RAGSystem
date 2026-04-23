import os
import shutil
import csv
import docx
from fastapi import UploadFile, HTTPException
from typing import List
from pypdf import PdfReader
from app.repositories.sql_repo import SQLRepository
from app.config import Config, get_logger

logger = get_logger(__name__)

class DocumentService:
    def __init__(self, sql_repo: SQLRepository, config: Config):
        self.sql_repo = sql_repo
        self.config = config
        self.upload_dir = config.upload_dir
        # Ensure the base upload directory always exists
        os.makedirs(self.upload_dir, exist_ok=True)

    async def save_upload(self, file: UploadFile):
        # Flatten folder uploads by extracting only the actual filename
        clean_name = file.filename.replace('\\', '/')
        safe_filename = clean_name.split('/')[-1]
        
        file_ext = safe_filename.split('.')[-1].upper() if '.' in safe_filename else "UNKNOWN"
        
        # Expanded allowed file types
        allowed_extensions = ["PDF", "DOCX", "TXT", "CSV"]
        if file_ext not in allowed_extensions:
            logger.warning(f"Rejected unsupported file: {safe_filename}")
            raise HTTPException(status_code=400, detail=f"Only {', '.join(allowed_extensions)} files are supported.")

        # Construct the full local path
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

    def _semantic_chunk_text(self, text: str, max_chars: int, overlap_chars: int) -> List[dict]:
        """
        Semantic Recursive Character Text Splitting with Overlap.
        Attempts to split on paragraphs, then sentences, then words.
        """
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

    def parse_and_chunk(self, document_id: str, chunk_size: int = 1024) -> List[dict]:
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
            
            # --- Expanded Document Parsing Logic ---
            if file_ext == "PDF":
                reader = PdfReader(file_path)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
                        
            elif file_ext == "DOCX":
                doc_obj = docx.Document(file_path)
                full_text = "\n".join([para.text for para in doc_obj.paragraphs])
                
            elif file_ext == "TXT":
                # 'ignore' prevents crashing on random weird bytes in plaintext
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    full_text = f.read()
                    
            elif file_ext == "CSV":
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        # Join columns with a readable separator for the LLM
                        full_text += " | ".join(row) + "\n"
            else:
                logger.warning(f"Unsupported file extraction for {doc.name}")
                return []

            # Fallback if no readable text is found
            if not full_text.strip():
                logger.warning(f"No parseable text found in {doc.name}. Might require OCR.")
                return [{"text": f"[Empty or Image-Only Document: {doc.name}]"}]

            # 2. Semantic Chunking with Overlap Logic
            char_chunk_size = chunk_size * 4
            overlap_chars = int(char_chunk_size * 0.1) # 10% context overlap
            
            logger.info(f"Semantic Chunking initiated for {doc.name} (Max Chars: {char_chunk_size}, Overlap: {overlap_chars})")
            
            chunks = self._semantic_chunk_text(full_text, char_chunk_size, overlap_chars)

            logger.info(f"Generated {len(chunks)} semantic chunks for document {doc.name}")
            return chunks

        except Exception as e:
            logger.error(f"Error parsing document {doc.name}: {e}")
            raise e