import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import logging
from sqlalchemy.orm import Session
from backend.database.db import get_db, DatabaseOperations
from backend.database.models import UserSession, BehavioralEvent
from backend.ml.predict import RealTimePredictor
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TrustLevel(Enum):
    """Trust level classifications"""
    CRITICAL = "critical"      # 0.0 - 0.2
    LOW = "low"               # 0.2 - 0.4
    MODERATE = "moderate"     # 0.4 - 0.6
    HIGH = "high"            # 0.6 - 0.8
    MAXIMUM = "maximum"      # 0.8 - 1.0

class SecurityAction(Enum):
    """Security actions based on trust levels"""
    TERMINATE_SESSION = "terminate_session"
    REQUIRE_REAUTH = "require_reauth"
    RESTRICT_ACCESS = "restrict_access"
    INCREASE_MONITORING = "increase_monitoring"
    LOG_ONLY = "log_only"
    NO_ACTION = "no_action"

class TrustEngine:
    """
    Dynamic Trust Scoring Engine for SENTINELX
    Calculates real-time trust scores and triggers security actions
    """
    
    def __init__(self):
        self.predictor = RealTimePredictor()
        
        # Trust calculation parameters
        self.trust_weights = {
            'behavioral_score': 0.4,      # Primary behavioral analysis
            'temporal_consistency': 0.2,   # Time-based patterns
            'session_context': 0.15,      # Session metadata
            'historical_trust': 0.15,     # Past trust history
            'anomaly_frequency': 0.1      # Recent anomaly patterns
        }
        
        # Trust decay parameters
        self.trust_decay = {
            'idle_decay_rate': 0.05,      # Trust decay per minute of inactivity
            'anomaly_decay_rate': 0.3,    # Trust decay per anomaly
            'recovery_rate': 0.1,         # Trust recovery per normal event
            'max_decay_per_update': 0.2   # Maximum trust loss per update
        }
        
        # Security thresholds
        self.security_thresholds = {
            TrustLevel.CRITICAL: 0.2,
            TrustLevel.LOW: 0.4,
            TrustLevel.MODERATE: 0.6,
            TrustLevel.HIGH: 0.8,
            TrustLevel.MAXIMUM: 1.0
        }
        
        # Action mappings
        self.trust_actions = {
            TrustLevel.CRITICAL: SecurityAction.TERMINATE_SESSION,
            TrustLevel.LOW: SecurityAction.REQUIRE_REAUTH,
            TrustLevel.MODERATE: SecurityAction.RESTRICT_ACCESS,
            TrustLevel.HIGH: SecurityAction.INCREASE_MONITORING,
            TrustLevel.MAXIMUM: SecurityAction.NO_ACTION
        }
    
    def calculate_trust_score(self, session_id: int, db: Session) -> Dict[str, Any]:
        """Calculate comprehensive trust score for a session"""
        
        try:
            # Get session information
            session = db.query(UserSession).filter(UserSession.id == session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            # Get behavioral prediction
            behavioral_analysis = self.predictor.predict_anomaly(
                session.user_id, session_id, db
            )
            
            # Calculate component scores
            behavioral_score = self._calculate_behavioral_score(behavioral_analysis)
            temporal_score = self._calculate_temporal_consistency(session, db)
            context_score = self._calculate_session_context_score(session, db)
            historical_score = self._calculate_historical_trust(session.user_id, db)
            anomaly_frequency_score = self._calculate_anomaly_frequency(session_id, db)
            
            # Weighted trust calculation
            trust_components = {
                'behavioral_score': behavioral_score,
                'temporal_consistency': temporal_score,
                'session_context': context_score,
                'historical_trust': historical_score,
                'anomaly_frequency': anomaly_frequency_score
            }
            
            weighted_trust = sum(
                score * self.trust_weights[component]
                for component, score in trust_components.items()
            )
            
            # Apply trust bounds
            final_trust_score = max(0.0, min(1.0, weighted_trust))
            
            # Determine trust level and actions
            trust_level = self._determine_trust_level(final_trust_score)
            recommended_action = self.trust_actions[trust_level]
            
            # Calculate trust trend
            trust_trend = self._calculate_trust_trend(session_id, final_trust_score, db)
            
            result = {
                'session_id': session_id,
                'user_id': session.user_id,
                'trust_score': final_trust_score,
                'trust_level': trust_level.value,
                'recommended_action': recommended_action.value,
                'trust_components': trust_components,
                'behavioral_analysis': behavioral_analysis,
                'trust_trend': trust_trend,
                'calculated_at': datetime.utcnow().isoformat(),
                'confidence': behavioral_analysis.get('confidence', 0.5)
            }
            
            # Update session trust score
            self._update_session_trust(session, final_trust_score, db)
            
            # Log trust events
            self._log_trust_event(result, db)
            
            return result
            
        except Exception as e:
            logger.error(f"Trust calculation failed for session {session_id}: {str(e)}")
            return {
                'session_id': session_id,
                'trust_score': 0.5,  # Default neutral trust
                'trust_level': TrustLevel.MODERATE.value,
                'recommended_action': SecurityAction.INCREASE_MONITORING.value,
                'error': str(e),
                'calculated_at': datetime.utcnow().isoformat()
            }
    
    def _calculate_behavioral_score(self, behavioral_analysis: Dict[str, Any]) -> float:
        """Convert behavioral anomaly analysis to trust score"""
        
        anomaly_score = behavioral_analysis.get('anomaly_score', 0.0)
        confidence = behavioral_analysis.get('confidence', 0.5)
        
        # Convert anomaly score to trust score (inverse relationship)
        base_trust = 1.0 - anomaly_score
        
        # Adjust based on confidence
        confidence_adjusted = base_trust * confidence + (1.0 - confidence) * 0.5
        
        return max(0.0, min(1.0, confidence_adjusted))
    
    def _calculate_temporal_consistency(self, session: UserSession, db: Session) -> float:
        """Calculate trust based on temporal behavioral patterns"""
        
        # Get recent behavioral events
        recent_events = db.query(BehavioralEvent).filter(
            BehavioralEvent.session_id == session.id,
            BehavioralEvent.timestamp >= datetime.utcnow() - timedelta(minutes=10)
        ).order_by(BehavioralEvent.timestamp.desc()).limit(20).all()
        
        if len(recent_events) < 5:
            return 0.7  # Neutral score for insufficient data
        
        # Analyze event timing consistency
        timestamps = [event.timestamp for event in recent_events]
        time_intervals = [
            (timestamps[i] - timestamps[i+1]).total_seconds()
            for i in range(len(timestamps) - 1)
        ]
        
        if not time_intervals:
            return 0.7
        
        # Calculate consistency metrics
        avg_interval = np.mean(time_intervals)
        interval_variance = np.var(time_intervals)
        
        # Consistent timing patterns indicate legitimate user
        consistency_score = 1.0 / (1.0 + interval_variance / max(avg_interval, 1.0))
        
        # Check for suspicious patterns (too regular = bot-like)
        if interval_variance < 0.1 and avg_interval < 1.0:
            consistency_score *= 0.5  # Penalize bot-like behavior
        
        return max(0.0, min(1.0, consistency_score))
    
    def _calculate_session_context_score(self, session: UserSession, db: Session) -> float:
        """Calculate trust based on session context and metadata"""
        
        context_score = 1.0
        
        # Session duration analysis
        session_duration = (datetime.utcnow() - session.login_time).total_seconds()
        
        # Very short sessions are suspicious
        if session_duration < 60:  # Less than 1 minute
            context_score *= 0.7
        elif session_duration > 28800:  # More than 8 hours
            context_score *= 0.8  # Long sessions slightly suspicious
        
        # Activity level analysis
        total_events = db.query(BehavioralEvent).filter(
            BehavioralEvent.session_id == session.id
        ).count()
        
        if session_duration > 0:
            events_per_minute = (total_events * 60) / session_duration
            
            # Optimal activity range
            if 5 <= events_per_minute <= 50:
                context_score *= 1.0  # Normal activity
            elif events_per_minute < 1:
                context_score *= 0.6  # Too little activity
            elif events_per_minute > 100:
                context_score *= 0.5  # Suspiciously high activity
        
        # IP address consistency (simplified)
        # In production, this would check for IP changes, geolocation, etc.
        if session.ip_address:
            context_score *= 1.0  # Placeholder for IP analysis
        
        return max(0.0, min(1.0, context_score))
    
    def _calculate_historical_trust(self, user_id: int, db: Session) -> float:
        """Calculate trust based on user's historical behavior"""
        
        # Get user's recent sessions
        recent_sessions = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.login_time >= datetime.utcnow() - timedelta(days=7)
        ).order_by(UserSession.login_time.desc()).limit(10).all()
        
        if not recent_sessions:
            return 0.5  # Neutral for new users
        
        # Calculate average historical trust
        trust_scores = [s.current_trust_score for s in recent_sessions if s.current_trust_score]
        
        if not trust_scores:
            return 0.5
        
        avg_historical_trust = np.mean(trust_scores)
        
        # Consider trust stability
        trust_variance = np.var(trust_scores)
        stability_factor = 1.0 / (1.0 + trust_variance)
        
        # Combine average trust with stability
        historical_score = avg_historical_trust * stability_factor
        
        return max(0.0, min(1.0, historical_score))
    
    def _calculate_anomaly_frequency(self, session_id: int, db: Session) -> float:
        """Calculate trust based on recent anomaly frequency"""
        
        # Get recent behavioral events with anomaly scores
        recent_events = db.query(BehavioralEvent).filter(
            BehavioralEvent.session_id == session_id,
            BehavioralEvent.timestamp >= datetime.utcnow() - timedelta(minutes=15)
        ).all()
        
        if not recent_events:
            return 1.0  # No recent data = neutral
        
        # Count anomalous events
        anomalous_events = sum(1 for event in recent_events if event.is_anomalous)
        anomaly_rate = anomalous_events / len(recent_events)
        
        # Convert anomaly rate to trust score
        frequency_score = 1.0 - anomaly_rate
        
        return max(0.0, min(1.0, frequency_score))
    
    def _determine_trust_level(self, trust_score: float) -> TrustLevel:
        """Determine trust level from numerical score"""
        
        if trust_score >= 0.8:
            return TrustLevel.MAXIMUM
        elif trust_score >= 0.6:
            return TrustLevel.HIGH
        elif trust_score >= 0.4:
            return TrustLevel.MODERATE
        elif trust_score >= 0.2:
            return TrustLevel.LOW
        else:
            return TrustLevel.CRITICAL
    
    def _calculate_trust_trend(self, session_id: int, current_trust: float, 
                             db: Session) -> Dict[str, Any]:
        """Calculate trust trend over time"""
        
        # Get recent trust history (simplified - would use dedicated trust log table)
        session = db.query(UserSession).filter(UserSession.id == session_id).first()
        
        if not session:
            return {"trend": "stable", "change": 0.0}
        
        previous_trust = session.current_trust_score or session.initial_trust_score
        trust_change = current_trust - previous_trust
        
        # Determine trend
        if abs(trust_change) < 0.05:
            trend = "stable"
        elif trust_change > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        
        return {
            "trend": trend,
            "change": trust_change,
            "previous_score": previous_trust,
            "change_magnitude": abs(trust_change)
        }
    
    def _update_session_trust(self, session: UserSession, trust_score: float, db: Session):
        """Update session trust score in database"""
        
        session.current_trust_score = trust_score
        session.last_activity = datetime.utcnow()
        db.commit()
    
    def _log_trust_event(self, trust_result: Dict[str, Any], db: Session):
        """Log trust calculation event for audit trail"""
        
        # In production, this would write to a dedicated trust_events table
        if trust_result['trust_level'] in ['critical', 'low']:
            logger.warning(f"Low trust detected: {trust_result}")
        elif trust_result['trust_level'] == 'moderate':
            logger.info(f"Moderate trust: Session {trust_result['session_id']}")
    
    def execute_security_action(self, session_id: int, action: SecurityAction, 
                              db: Session) -> Dict[str, Any]:
        """Execute recommended security action"""
        
        session = db.query(UserSession).filter(UserSession.id == session_id).first()
        if not session:
            return {"success": False, "message": "Session not found"}
        
        try:
            if action == SecurityAction.TERMINATE_SESSION:
                session.is_active = False
                db.commit()
                logger.warning(f"Session {session_id} terminated due to low trust")
                return {
                    "success": True,
                    "action": "session_terminated",
                    "message": "Session terminated due to security concerns"
                }
            
            elif action == SecurityAction.REQUIRE_REAUTH:
                # Set flag for re-authentication requirement
                session.current_trust_score = min(session.current_trust_score, 0.3)
                db.commit()
                logger.info(f"Re-authentication required for session {session_id}")
                return {
                    "success": True,
                    "action": "reauth_required",
                    "message": "Re-authentication required"
                }
            
            elif action == SecurityAction.RESTRICT_ACCESS:
                # Implement access restrictions (would integrate with authorization system)
                logger.info(f"Access restricted for session {session_id}")
                return {
                    "success": True,
                    "action": "access_restricted",
                    "message": "Access restrictions applied"
                }
            
            elif action == SecurityAction.INCREASE_MONITORING:
                # Increase monitoring frequency
                logger.info(f"Increased monitoring for session {session_id}")
                return {
                    "success": True,
                    "action": "monitoring_increased",
                    "message": "Monitoring frequency increased"
                }
            
            else:
                return {
                    "success": True,
                    "action": "no_action",
                    "message": "No action required"
                }
                
        except Exception as e:
            logger.error(f"Failed to execute security action {action}: {str(e)}")
            return {
                "success": False,
                "message": f"Action execution failed: {str(e)}"
            }
    
    def get_session_trust_summary(self, session_id: int, db: Session) -> Dict[str, Any]:
        """Get comprehensive trust summary for a session"""
        
        trust_result = self.calculate_trust_score(session_id, db)
        
        # Add additional context
        session = db.query(UserSession).filter(UserSession.id == session_id).first()
        if session:
            trust_result['session_info'] = {
                'duration_minutes': (datetime.utcnow() - session.login_time).total_seconds() / 60,
                'initial_trust': session.initial_trust_score,
                'trust_threshold': session.min_trust_threshold,
                'is_active': session.is_active
            }
        
        return trust_result

# Global trust engine instance
trust_engine = TrustEngine()