from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from pydantic import BaseModel
from app.dependencies import get_db
from app.models import UserModel
from app.config import get_logger

logger = get_logger(__name__)
router = APIRouter()

class AdminLoginRequest(BaseModel):
    username: str
    password: str

@router.post("/admin")
async def admin_login(req: AdminLoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.email == req.username, UserModel.password == req.password).first()
    
    if not user or user.role != 'admin':
        logger.warning(f"Failed admin login attempt for username: {req.username}")
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
        
    return {
        "status": "success", 
        "token": f"admin-secret-token-{user.id}", 
        "user": {"id": user.id, "name": user.name, "role": user.role}
    }

@router.post("/google")
async def google_login(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    token = data.get("token")
    
    if not token:
        raise HTTPException(status_code=400, detail="Token missing")
        
    try:
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request())
        user_id = idinfo['sub']
        
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            user = UserModel(
                id=user_id,
                email=idinfo.get('email'),
                name=idinfo.get('name'),
                picture=idinfo.get('picture'),
                role='user'
            )
            db.add(user)
            db.commit()
            
        return {"status": "success", "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role}}
    except Exception as e:
        logger.error(f"Google auth failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid Google Token")