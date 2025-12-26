from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database.db import get_db, DatabaseOperations
from ..database.models import BehavioralEvent
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import numpy as np
from datetime import datetime

router = APIRouter()

class KeystrokeData(BaseModel):
    eventType: str
    rawData: List[Dict[str, Any]]
    features: Dict[str, float]
    sessionToken: str
    timestamp: int

class KeystrokeProcessor:
    
    @staticmethod
    def extract_advanced_features(raw_keystrokes: List[Dict]) -> Dict[str, float]:
        """Extract advanced keystroke dynamics features"""
        if len(raw_keystrokes) < 5:
            return {}
        
        dwell_times = [k['dwellTime'] for k in raw_keystrokes if 'dwellTime' in k]
        flight_times = [k['flightTime'] for k in raw_keystrokes if k.get('flightTime')]
        
        if not dwell_times:
            return {}
        
        features = {}
        
        # Basic timing features
        features['avg_dwell_time'] = np.mean(dwell_times)
        features['std_dwell_time'] = np.std(dwell_times)
        features['min_dwell_time'] = np.min(dwell_times)
        features['max_dwell_time'] = np.max(dwell_times)
        
        if flight_times:
            features['avg_flight_time'] = np.mean(flight_times)
            features['std_flight_time'] = np.std(flight_times)
            features['min_flight_time'] = np.min(flight_times)
            features['max_flight_time'] = np.max(flight_times)
        
        # Rhythm and pattern features
        features['typing_rhythm_variance'] = KeystrokeProcessor.calculate_rhythm_variance(raw_keystrokes)
        features['pressure_consistency'] = KeystrokeProcessor.calculate_pressure_consistency(dwell_times)
        features['typing_cadence'] = KeystrokeProcessor.calculate_typing_cadence(raw_keystrokes)
        
        # Behavioral patterns
        features['special_key_ratio'] = sum(1 for k in raw_keystrokes if k.get('isSpecialKey', False)) / len(raw_keystrokes)
        features['error_correction_rate'] = KeystrokeProcessor.calculate_error_rate(raw_keystrokes)
        
        return features
    
    @staticmethod
    def calculate_rhythm_variance(keystrokes: List[Dict]) -> float:
        """Calculate variance in typing rhythm"""
        if len(keystrokes) < 3:
            return 0.0
        
        intervals = []
        for i in range(1, len(keystrokes)):
            if keystrokes[i].get('flightTime'):
                intervals.append(keystrokes[i]['flightTime'])
        
        return np.var(intervals) if intervals else 0.0
    
    @staticmethod
    def calculate_pressure_consistency(dwell_times: List[float]) -> float:
        """Calculate consistency in key press pressure (dwell time variance)"""
        if len(dwell_times) < 2:
            return 1.0
        
        coefficient_of_variation = np.std(dwell_times) / np.mean(dwell_times)
        return 1.0 / (1.0 + coefficient_of_variation)  # Higher = more consistent
    
    @staticmethod
    def calculate_typing_cadence(keystrokes: List[Dict]) -> float:
        """Calculate overall typing cadence (keys per second)"""
        if len(keystrokes) < 2:
            return 0.0
        
        time_span = (keystrokes[-1]['timestamp'] - keystrokes[0]['timestamp']) / 1000.0  # Convert to seconds
        return len(keystrokes) / time_span if time_span > 0 else 0.0
    
    @staticmethod
    def calculate_error_rate(keystrokes: List[Dict]) -> float:
        """Estimate error correction rate based on backspace usage"""
        backspace_count = sum(1 for k in keystrokes if k.get('keyCode') == 'Backspace')
        return backspace_count / len(keystrokes) if keystrokes else 0.0
    
    @staticmethod
    def create_behavioral_signature(features: Dict[str, float]) -> str:
        """Create a compact behavioral signature for comparison"""
        key_features = [
            'avg_dwell_time', 'avg_flight_time', 'typing_rhythm_variance',
            'pressure_consistency', 'typing_cadence'
        ]
        
        signature_values = []
        for feature in key_features:
            if feature in features:
                # Normalize and quantize features for signature
                normalized = min(max(features[feature], 0), 1000)  # Clamp values
                quantized = int(normalized / 10)  # Reduce precision
                signature_values.append(str(quantized))
        
        return '_'.join(signature_values)

@router.post("/keystroke")
async def process_keystroke_data(
    data: KeystrokeData,
    db: Session = Depends(get_db)
):
    """Process incoming keystroke behavioral data"""
    try:
        # Get session from token
        session = DatabaseOperations.get_active_session(db, data.sessionToken)
        if not session:
            raise HTTPException(status_code=401, detail="Invalid session token")
        
        # Extract advanced features
        advanced_features = KeystrokeProcessor.extract_advanced_features(data.rawData)
        
        # Combine with basic features
        all_features = {**data.features, **advanced_features}
        
        # Create behavioral signature
        signature = KeystrokeProcessor.create_behavioral_signature(all_features)
        
        # Store behavioral event
        behavioral_event = BehavioralEvent(
            session_id=session.id,
            event_type="keystroke",
            event_data=json.dumps(data.rawData),
            processed_features=json.dumps(all_features),
            timestamp=datetime.fromtimestamp(data.timestamp / 1000)
        )
        
        db.add(behavioral_event)
        db.commit()
        
        return {
            "status": "success",
            "message": f"Processed {len(data.rawData)} keystroke events",
            "features_extracted": len(all_features),
            "behavioral_signature": signature,
            "event_id": behavioral_event.id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@router.get("/keystroke/profile/{user_id}")
async def get_keystroke_profile(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get keystroke behavioral profile for a user"""
    try:
        # Get user's behavioral events
        events = db.query(BehavioralEvent).join(
            BehavioralEvent.session
        ).filter(
            BehavioralEvent.event_type == "keystroke",
            BehavioralEvent.session.has(user_id=user_id)
        ).limit(100).all()
        
        if not events:
            return {"profile": None, "message": "No keystroke data available"}
        
        # Aggregate features across all events
        all_features = []
        for event in events:
            try:
                features = json.loads(event.processed_features)
                all_features.append(features)
            except:
                continue
        
        if not all_features:
            return {"profile": None, "message": "No valid feature data"}
        
        # Calculate profile statistics
        profile = KeystrokeProcessor.calculate_profile_statistics(all_features)
        
        return {
            "profile": profile,
            "sample_count": len(all_features),
            "last_updated": events[-1].timestamp.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile retrieval failed: {str(e)}")
    
    @staticmethod
    def calculate_profile_statistics(feature_sets: List[Dict]) -> Dict:
        """Calculate statistical profile from multiple feature sets"""
        if not feature_sets:
            return {}
        
        # Get all unique feature names
        all_features = set()
        for fs in feature_sets:
            all_features.update(fs.keys())
        
        profile = {}
        for feature in all_features:
            values = [fs.get(feature, 0) for fs in feature_sets if feature in fs]
            if values:
                profile[f"{feature}_mean"] = np.mean(values)
                profile[f"{feature}_std"] = np.std(values)
                profile[f"{feature}_min"] = np.min(values)
                profile[f"{feature}_max"] = np.max(values)
        
        return profile