from fastapi import APIRouter, Depends, HTTPException
from app.schemas import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.dependencies import get_chat_service, get_current_user
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
        # Validate query
        if not request.query or not request.query.strip():
            raise HTTPException(
                status_code=400,
                detail="Query cannot be empty.",
            )

        logger.info(
            f"Received chat query: {request.query[:50]}..."
        )

        # Process query with session memory
        response = await chat_svc.process_query(
            request.query,
            request.session_id,
            user_id,
        )

        return response

    except HTTPException:
        # Re-raise FastAPI HTTP exceptions directly
        raise

    except Exception as e:
        logger.exception(f"Chat error: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail="Failed to process chat query.",
        )