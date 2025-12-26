from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    behavioral_profiles = relationship("BehavioralProfile", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")

class BehavioralProfile(Base):
    __tablename__ = "behavioral_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Keystroke Features
    avg_dwell_time = Column(Float)  # Average key press duration
    avg_flight_time = Column(Float)  # Average time between keystrokes
    typing_rhythm_pattern = Column(Text)  # JSON string of rhythm patterns
    
    # Mouse Features
    avg_mouse_speed = Column(Float)
    mouse_movement_pattern = Column(Text)  # JSON string of movement patterns
    click_pressure_pattern = Column(Text)  # JSON string of click patterns
    
    # Profile Metadata
    samples_count = Column(Integer, default=0)
    confidence_score = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="behavioral_profiles")

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_token = Column(String(255), unique=True, nullable=False)
    
    # Trust Scoring
    initial_trust_score = Column(Float, default=1.0)
    current_trust_score = Column(Float, default=1.0)
    min_trust_threshold = Column(Float, default=0.3)
    
    # Session Metadata
    ip_address = Column(String(45))
    user_agent = Column(Text)
    login_time = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    behavioral_events = relationship("BehavioralEvent", back_populates="session")

class BehavioralEvent(Base):
    __tablename__ = "behavioral_events"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("user_sessions.id"), nullable=False)
    
    # Event Data
    event_type = Column(String(20))  # 'keystroke' or 'mouse'
    event_data = Column(Text)  # JSON string of raw event data
    processed_features = Column(Text)  # JSON string of extracted features
    
    # Anomaly Detection
    anomaly_score = Column(Float)
    is_anomalous = Column(Boolean, default=False)
    
    # Timing
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("UserSession", back_populates="behavioral_events")