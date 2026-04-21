import os
import shutil
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
        # FIX: Flatten folder uploads by extracting only the actual filename
        # This prevents Windows path errors like 'pdf\filename.pdf'
        clean_name = file.filename.replace('\\', '/')
        safe_filename = clean_name.split('/')[-1]
        
        file_ext = safe_filename.split('.')[-1].upper() if '.' in safe_filename else "UNKNOWN"
        
        # Restrict system to PDF files only for now
        if file_ext != "PDF":
            logger.warning(f"Rejected non-PDF file: {safe_filename}")
            raise HTTPException(status_code=400, detail="Only PDF files are supported at this time.")

        # Construct the full local path using the flattened filename
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

    def parse_and_chunk(self, document_id: str, chunk_size: int) -> List[dict]:
        doc = self.sql_repo.get_document(document_id)
        if not doc:
            logger.warning(f"Cannot chunk unknown document {document_id}")
            return []

        file_path = os.path.join(self.upload_dir, doc.name)
        if not os.path.exists(file_path):
            logger.error(f"File not found on disk: {file_path}")
            return []

        logger.info(f"Parsing and chunking PDF document {doc.name}")
        
        try:
            # 1. Read PDF Text
            reader = PdfReader(file_path)
            full_text = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

            # Fallback if no readable text is found
            if not full_text.strip():
                logger.warning(f"No parseable text found in {doc.name}. Might require OCR.")
                return [{"text": f"[Empty or Image-Only PDF: {doc.name}]"}]

            # 2. Chunking Logic
            char_chunk_size = chunk_size * 4
            chunks = []
            
            for i in range(0, len(full_text), char_chunk_size):
                chunk_text = full_text[i:i + char_chunk_size].strip()
                if chunk_text:
                    chunks.append({"text": chunk_text})

            logger.info(f"Generated {len(chunks)} chunks for {doc.name}")
            return chunks

        except Exception as e:
            logger.error(f"Error parsing PDF {doc.name}: {e}")
            raise e