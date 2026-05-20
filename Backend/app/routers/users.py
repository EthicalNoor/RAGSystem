from fastapi import APIRouter, Depends, HTTPException
from app.schemas import UserResponse
from app.dependencies import get_sql_repo, get_current_user
from app.repositories.sql_repo import SQLRepository

router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    user_id: str = Depends(get_current_user),
    sql_repo: SQLRepository = Depends(get_sql_repo)
):
    user = sql_repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user