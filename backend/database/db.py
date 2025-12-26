from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from backend.database.models import Base, User, BehavioralProfile, UserSession, BehavioralEvent
import os
from pathlib import Path

# Database Configuration
DATABASE_URL = "sqlite:///./sentinelx.db"

# Create database engine
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}  # Needed for SQLite
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_database():
    """Initialize database with tables"""
    try:
        create_tables()
        print("🗄️ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")

# Database Operations
class DatabaseOperations:
    
    @staticmethod
    def create_user(db: Session, username: str, email: str, hashed_password: str):
        """Create a new user"""
        db_user = User(
            username=username,
            email=email,
            hashed_password=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    
    @staticmethod
    def get_user_by_username(db: Session, username: str):
        """Get user by username"""
        return db.query(User).filter(User.username == username).first()
    
    @staticmethod
    def get_user_by_email(db: Session, email: str):
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    def create_session(db: Session, user_id: int, session_token: str, ip_address: str = None, user_agent: str = None):
        """Create a new user session"""
        db_session = UserSession(
            user_id=user_id,
            session_token=session_token,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        return db_session
    
    @staticmethod
    def get_active_session(db: Session, session_token: str):
        """Get active session by token"""
        return db.query(UserSession).filter(
            UserSession.session_token == session_token,
            UserSession.is_active == True
        ).first()
    
    @staticmethod
    def update_trust_score(db: Session, session_id: int, new_trust_score: float):
        """Update session trust score"""
        session = db.query(UserSession).filter(UserSession.id == session_id).first()
        if session:
            session.current_trust_score = new_trust_score
            db.commit()
        return session

if __name__ == "__main__":
    # Initialize database when run directly
    init_database()