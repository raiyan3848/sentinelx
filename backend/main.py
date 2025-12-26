from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import json
import asyncio
from typing import Dict, List

# Import routers and dependencies
from backend.auth.login import router as auth_router, get_current_user
from backend.behavior.keystroke import router as keystroke_router
from backend.behavior.mouse import router as mouse_router
from backend.database.db import get_db, init_database
from backend.database.models import User
from backend.trust.trust_engine import trust_engine
from backend.ml.predict import predictor

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_token: str):
        await websocket.accept()
        self.active_connections[session_token] = websocket
    
    def disconnect(self, session_token: str):
        if session_token in self.active_connections:
            del self.active_connections[session_token]
    
    async def send_personal_message(self, message: dict, session_token: str):
        if session_token in self.active_connections:
            try:
                await self.active_connections[session_token].send_text(json.dumps(message))
            except:
                self.disconnect(session_token)
    
    async def broadcast(self, message: dict):
        disconnected = []
        for session_token, connection in self.active_connections.items():
            try:
                await connection.send_text(json.dumps(message))
            except:
                disconnected.append(session_token)
        
        for session_token in disconnected:
            self.disconnect(session_token)

manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting SENTINELX...")
    init_database()
    print("✅ Database initialized")
    yield
    # Shutdown
    print("🛑 Shutting down SENTINELX...")

# Create FastAPI app
app = FastAPI(
    title="SENTINELX API",
    description="Behavioral Biometric Authentication System",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(keystroke_router, prefix="/api/behavior", tags=["Behavioral Data"])
app.include_router(mouse_router, prefix="/api/behavior", tags=["Behavioral Data"])

# Trust Score Endpoints
@app.post("/api/trust/score", tags=["Trust Engine"])
async def calculate_trust_score(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate trust score for current session"""
    try:
        session_token = request.get("sessionToken")
        if not session_token:
            raise HTTPException(status_code=400, detail="Session token required")
        
        # Get session from token
        from backend.database.db import DatabaseOperations
        session = DatabaseOperations.get_active_session(db, session_token)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Calculate trust score
        trust_result = trust_engine.calculate_trust_score(session.id, db)
        
        # Send real-time update via WebSocket
        await manager.send_personal_message({
            "type": "trust_update",
            "data": trust_result
        }, session_token)
        
        return trust_result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trust/history/{user_id}", tags=["Trust Engine"])
async def get_trust_history(
    user_id: int,
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get trust score history for user"""
    # Implementation for trust history
    return {"message": "Trust history endpoint", "user_id": user_id, "days": days}

# Security Action Endpoints
@app.post("/api/security/action", tags=["Security"])
async def execute_security_action(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Execute security action"""
    try:
        session_id = request.get("sessionId")
        action = request.get("action")
        
        if not session_id or not action:
            raise HTTPException(status_code=400, detail="Session ID and action required")
        
        from backend.trust.trust_engine import SecurityAction
        security_action = SecurityAction(action)
        
        result = trust_engine.execute_security_action(session_id, security_action, db)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ML Model Endpoints
@app.get("/api/ml/model/status/{user_id}", tags=["Machine Learning"])
async def get_model_status(
    user_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get ML model status for user"""
    status = predictor.get_model_status(user_id)
    return status

@app.post("/api/ml/model/train/{user_id}", tags=["Machine Learning"])
async def train_user_model(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Train ML model for specific user"""
    try:
        from backend.ml.train_model import BehavioralAnomalyDetector
        detector = BehavioralAnomalyDetector()
        result = detector.train_user_model(user_id, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Session Management
@app.get("/api/session/{session_id}", tags=["Session"])
async def get_session_info(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get session information"""
    from backend.database.models import UserSession
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "id": session.id,
        "user_id": session.user_id,
        "current_trust_score": session.current_trust_score,
        "login_time": session.login_time,
        "last_activity": session.last_activity,
        "is_active": session.is_active
    }

@app.put("/api/session/activity", tags=["Session"])
async def update_session_activity(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update session activity timestamp"""
    try:
        session_token = request.get("sessionToken")
        if not session_token:
            raise HTTPException(status_code=400, detail="Session token required")
        
        from backend.database.db import DatabaseOperations
        from datetime import datetime
        
        session = DatabaseOperations.get_active_session(db, session_token)
        if session:
            session.last_activity = datetime.utcnow()
            db.commit()
            return {"status": "updated"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket endpoint for real-time updates
@app.websocket("/ws/{session_token}")
async def websocket_endpoint(websocket: WebSocket, session_token: str):
    await manager.connect(websocket, session_token)
    try:
        while True:
            # Keep connection alive and listen for messages
            data = await websocket.receive_text()
            # Echo back for testing
            await websocket.send_text(f"Message received: {data}")
    except WebSocketDisconnect:
        manager.disconnect(session_token)

# Health check endpoint
@app.get("/api/health", tags=["System"])
async def health_check():
    """System health check"""
    return {
        "status": "healthy",
        "service": "SENTINELX",
        "version": "1.0.0"
    }

# Analytics endpoints
@app.get("/api/analytics/behavioral/{user_id}", tags=["Analytics"])
async def get_behavioral_analytics(
    user_id: int,
    range: str = "24h",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get behavioral analytics for user"""
    # Implementation for behavioral analytics
    return {
        "user_id": user_id,
        "range": range,
        "keystroke_metrics": {
            "avg_typing_speed": 65,
            "rhythm_consistency": 87,
            "error_rate": 0.03
        },
        "mouse_metrics": {
            "avg_speed": 250,
            "click_precision": 92,
            "movement_smoothness": 0.85
        }
    }

@app.get("/api/analytics/system", tags=["Analytics"])
async def get_system_metrics():
    """Get system-wide metrics"""
    return {
        "active_sessions": len(manager.active_connections),
        "total_users": 0,  # Would query database
        "avg_trust_score": 0.85,
        "threat_level": "low"
    }

# Mount static files (frontend)
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)