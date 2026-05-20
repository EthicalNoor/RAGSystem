from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.schemas import ChatRequest, ChatResponse, ChatSessionResponse, QueryLogResponse, FeedbackRequest
from app.services.chat_service import ChatService
from app.dependencies import get_chat_service, get_current_user, get_sql_repo
from app.repositories.sql_repo import SQLRepository
from app.config import get_logger

logger = get_logger(__name__)
router = APIRouter()

@router.post("", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    chat_svc: ChatService = Depends(get_chat_service),
    user_id: str = Depends(get_current_user),
):
    try:
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty.")

        logger.info(f"Received chat query: {request.query[:50]}...")
        response = await chat_svc.process_query(request.query, request.session_id, user_id)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process chat query.")

@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    sql_repo: SQLRepository = Depends(get_sql_repo),
    user_id: str = Depends(get_current_user)
):
    return sql_repo.get_chat_sessions(user_id)

@router.get("/sessions/{session_id}", response_model=List[QueryLogResponse])
async def get_session_history(
    session_id: str,
    sql_repo: SQLRepository = Depends(get_sql_repo),
    user_id: str = Depends(get_current_user)
):
    return sql_repo.get_session_history(session_id, user_id)

@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    sql_repo: SQLRepository = Depends(get_sql_repo),
    user_id: str = Depends(get_current_user)
):
    success = sql_repo.delete_chat_session(session_id, user_id)
    if success:
        return {"status": "success", "message": "Session deleted."}
    raise HTTPException(status_code=404, detail="Session not found or unauthorized.")

@router.delete("/history")
async def clear_personal_chat_history(
    sql_repo: SQLRepository = Depends(get_sql_repo),
    user_id: str = Depends(get_current_user)
):
    try:
        sql_repo.delete_user_query_logs(user_id)
        return {"status": "success", "message": "Personal chat history cleared successfully."}
    except Exception as e:
        logger.error(f"Error clearing history for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to clear history.")

@router.post("/messages/{message_id}/feedback")
async def submit_message_feedback(
    message_id: str,
    payload: FeedbackRequest,
    sql_repo: SQLRepository = Depends(get_sql_repo),
    user_id: str = Depends(get_current_user)
):
    success = sql_repo.update_message_feedback(message_id, payload.score, payload.text, user_id)
    if success:
        return {"status": "success", "message": "Feedback recorded."}
    raise HTTPException(status_code=404, detail="Message not found or unauthorized.")