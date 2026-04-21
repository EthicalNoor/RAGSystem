from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from typing import List
from app.schemas import DocumentResponse
from app.services.rag_service import RAGService
from app.dependencies import get_rag_service, get_sql_repo
from app.repositories.sql_repo import SQLRepository
from app.config import get_logger

logger = get_logger(__name__)
router = APIRouter()

@router.post("/upload", response_model=List[DocumentResponse])
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    rag_svc: RAGService = Depends(get_rag_service)
):
    try:
        # Save files and get back Database Models
        documents = await rag_svc.handle_uploads(files)
        
        # Process vector embeddings in the background
        background_tasks.add_task(rag_svc.process_documents, [doc.id for doc in documents])
        
        # FIX: Explicitly map DB Model fields to the Pydantic Schema
        return [
            DocumentResponse(
                id=d.id, 
                name=d.name, 
                type=d.file_type, 
                size=f"{d.size_mb:.2f} MB", 
                status=d.status
            ) for d in documents
        ]
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Document upload failed.")

@router.post("/upload-folder", response_model=List[DocumentResponse])
async def upload_folder(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    rag_svc: RAGService = Depends(get_rag_service)
):
    return await upload_documents(background_tasks, files, rag_svc)

@router.get("", response_model=List[DocumentResponse])
async def get_all_documents(sql_repo: SQLRepository = Depends(get_sql_repo)):
    docs = sql_repo.get_all_documents()
    return [
        DocumentResponse(
            id=d.id, name=d.name, type=d.file_type, 
            size=f"{d.size_mb:.2f} MB", status=d.status
        ) for d in docs
    ]

@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    rag_svc: RAGService = Depends(get_rag_service)
):
    try:
        success = rag_svc.delete_document(document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found.")
        return {"status": "success", "message": "Document deleted."}
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Deletion failed.")