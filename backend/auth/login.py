from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from backend.database.db import get_db, DatabaseOperations
from backend.database.models import User
import secrets

# Security Configuration
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

class AuthService:
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: timedelta = None):
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str):
        """Authenticate user with username and password"""
        user = DatabaseOperations.get_user_by_username(db, username)
        if not user:
            return False
        if not AuthService.verify_password(password, user.hashed_password):
            return False
        return user
    
    @staticmethod
    def register_user(db: Session, username: str, email: str, password: str):
        """Register a new user"""
        # Check if user already exists
        if DatabaseOperations.get_user_by_username(db, username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        
        if DatabaseOperations.get_user_by_email(db, email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create new user
        hashed_password = AuthService.get_password_hash(password)
        user = DatabaseOperations.create_user(
            db=db,
            username=username,
            email=email,
            hashed_password=hashed_password
        )
        return user
    
    @staticmethod
    def login_user(db: Session, username: str, password: str, ip_address: str = None, user_agent: str = None):
        """Login user and create session"""
        # Authenticate user
        user = AuthService.authenticate_user(db, username, password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = AuthService.create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        
        # Create session
        session_token = secrets.token_urlsafe(32)
        session = DatabaseOperations.create_session(
            db=db,
            user_id=user.id,
            session_token=session_token,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return {
            "access_token": access_token,
            "session_token": session_token,
            "token_type": "bearer",
            "user_id": user.id,
            "username": user.username
        }

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = DatabaseOperations.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user

# Add FastAPI router and endpoints
from fastapi import APIRouter
from pydantic import BaseModel

# Create router
router = APIRouter()

# Pydantic models
class UserLogin(BaseModel):
    username: str
    password: str

class UserRegister(BaseModel):
    username: str
    email: str
    password: str

# API Endpoints
@router.post("/login")
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """User login endpoint"""
    try:
        result = AuthService.login_user(
            db=db,
            username=user_data.username,
            password=user_data.password
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/register")
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """User registration endpoint"""
    try:
        user = AuthService.register_user(
            db=db,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password
        )
        return {
            "message": "User registered successfully",
            "user_id": user.id,
            "username": user.username
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at
    }

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """User logout endpoint"""
    # In a real implementation, you would invalidate the session token
    return {"message": "Logged out successfully"}