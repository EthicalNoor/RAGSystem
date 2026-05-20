from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from typing import List
from app.schemas import DocumentResponse, DocumentDetailResponse
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
        documents = await rag_svc.handle_uploads(files)
        background_tasks.add_task(rag_svc.process_documents, [doc.id for doc in documents])
        return [
            DocumentResponse(id=d.id, name=d.name, type=d.file_type, size=f"{d.size_mb:.2f} MB", status=d.status) for d in documents
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
        DocumentResponse(id=d.id, name=d.name, type=d.file_type, size=f"{d.size_mb:.2f} MB", status=d.status) for d in docs
    ]

@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document_details(
    document_id: str,
    sql_repo: SQLRepository = Depends(get_sql_repo)
):
    doc = sql_repo.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    chunk_count = sql_repo.get_document_chunks_count(document_id)
    edge_count = sql_repo.get_document_edges_count(document_id)
    
    return DocumentDetailResponse(
        id=doc.id, name=doc.name, type=doc.file_type, size=f"{doc.size_mb:.2f} MB", 
        status=doc.status, chunk_count=chunk_count, graph_edge_count=edge_count
    )

@router.post("/{document_id}/reindex")
async def reindex_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    sql_repo: SQLRepository = Depends(get_sql_repo),
    rag_svc: RAGService = Depends(get_rag_service)
):
    doc = sql_repo.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Clear old data before re-processing
    sql_repo.clear_document_data(document_id)
    sql_repo.update_document_status(document_id, "Pending Reindex")
    
    background_tasks.add_task(rag_svc.process_documents, [document_id])
    return {"status": "success", "message": "Document reindexing started in background."}

@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    rag_svc: RAGService = Depends(get_rag_service)
):
    try:
        success = rag_svc.delete_document(document_id)
        if not success:
            return {"status": "success", "message": "Document already deleted."}
        return {"status": "success", "message": "Document deleted."}
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Deletion failed.")