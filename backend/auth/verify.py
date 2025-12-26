from fastapi import HTTPException, Depends, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from backend.database.db import get_db, DatabaseOperations
from backend.database.models import User, UserSession
from backend.ml.predict import predictor
from backend.trust.trust_engine import trust_engine
import logging

logger = logging.getLogger(__name__)

class SessionVerifier:
    """
    Session verification and continuous authentication
    """
    
    @staticmethod
    def verify_session_token(session_token: str, db: Session) -> UserSession:
        """Verify session token and return session"""
        session = DatabaseOperations.get_active_session(db, session_token)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session"
            )
        
        # Check if session is still active
        if not session.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been terminated"
            )
        
        # Check session timeout (24 hours)
        session_age = datetime.utcnow() - session.login_time
        if session_age > timedelta(hours=24):
            session.is_active = False
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired"
            )
        
        return session
    
    @staticmethod
    def verify_trust_level(session: UserSession, db: Session) -> dict:
        """Verify current trust level for session"""
        try:
            # Calculate current trust score
            trust_result = trust_engine.calculate_trust_score(session.id, db)
            
            # Check if trust is below minimum threshold
            if trust_result['trust_score'] < session.min_trust_threshold:
                logger.warning(f"Trust below threshold for session {session.id}: {trust_result['trust_score']}")
                
                return {
                    "verified": False,
                    "trust_score": trust_result['trust_score'],
                    "trust_level": trust_result['trust_level'],
                    "action_required": trust_result['recommended_action']
                }
            
            return {
                "verified": True,
                "trust_score": trust_result['trust_score'],
                "trust_level": trust_result['trust_level'],
                "action_required": "no_action"
            }
            
        except Exception as e:
            logger.error(f"Trust verification failed for session {session.id}: {str(e)}")
            return {
                "verified": False,
                "trust_score": 0.0,
                "trust_level": "unknown",
                "action_required": "increase_monitoring",
                "error": str(e)
            }
    
    @staticmethod
    def continuous_verification(session_token: str, db: Session) -> dict:
        """Perform continuous authentication verification"""
        
        # Verify session token
        session = SessionVerifier.verify_session_token(session_token, db)
        
        # Verify trust level
        trust_verification = SessionVerifier.verify_trust_level(session, db)
        
        # Update session activity
        session.last_activity = datetime.utcnow()
        db.commit()
        
        return {
            "session_id": session.id,
            "user_id": session.user_id,
            "session_verified": True,
            "trust_verification": trust_verification,
            "last_activity": session.last_activity
        }
    
    @staticmethod
    def check_behavioral_anomaly(user_id: int, session_id: int, db: Session) -> dict:
        """Check for behavioral anomalies in current session"""
        try:
            # Get anomaly prediction
            anomaly_result = predictor.predict_anomaly(user_id, session_id, db)
            
            # Determine if anomaly is significant
            is_anomalous = anomaly_result.get('risk_level') in ['medium_risk', 'high_risk']
            
            return {
                "anomaly_detected": is_anomalous,
                "anomaly_score": anomaly_result.get('anomaly_score', 0.0),
                "risk_level": anomaly_result.get('risk_level', 'normal'),
                "confidence": anomaly_result.get('confidence', 0.0),
                "details": anomaly_result
            }
            
        except Exception as e:
            logger.error(f"Behavioral anomaly check failed: {str(e)}")
            return {
                "anomaly_detected": False,
                "anomaly_score": 0.0,
                "risk_level": "unknown",
                "confidence": 0.0,
                "error": str(e)
            }

# Dependency for continuous verification
def verify_continuous_auth(session_token: str, db: Session = Depends(get_db)) -> dict:
    """FastAPI dependency for continuous authentication"""
    return SessionVerifier.continuous_verification(session_token, db)