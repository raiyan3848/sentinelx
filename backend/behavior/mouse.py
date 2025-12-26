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

class MouseData(BaseModel):
    eventType: str
    rawData: List[Dict[str, Any]]
    features: Dict[str, float]
    sessionToken: str
    timestamp: int

class MouseProcessor:
    
    @staticmethod
    def extract_advanced_features(raw_mouse_data: List[Dict]) -> Dict[str, float]:
        """Extract advanced mouse behavioral features"""
        if len(raw_mouse_data) < 10:
            return {}
        
        move_events = [e for e in raw_mouse_data if e.get('type') == 'move']
        click_events = [e for e in raw_mouse_data if e.get('type') == 'click']
        
        if len(move_events) < 5:
            return {}
        
        features = {}
        
        # Movement pattern features
        velocities = [e['velocity'] for e in move_events if e.get('velocity', 0) > 0]
        distances = [e['distance'] for e in move_events if e.get('distance', 0) > 0]
        
        if velocities:
            features['velocity_mean'] = np.mean(velocities)
            features['velocity_std'] = np.std(velocities)
            features['velocity_skewness'] = MouseProcessor.calculate_skewness(velocities)
            features['velocity_kurtosis'] = MouseProcessor.calculate_kurtosis(velocities)
        
        # Movement trajectory features
        features['path_efficiency'] = MouseProcessor.calculate_path_efficiency(move_events)
        features['movement_smoothness'] = MouseProcessor.calculate_movement_smoothness(move_events)
        features['direction_consistency'] = MouseProcessor.calculate_direction_consistency(move_events)
        
        # Click pattern features
        if click_events:
            features['click_precision'] = MouseProcessor.calculate_click_precision(click_events)
            features['double_click_rate'] = MouseProcessor.calculate_double_click_rate(click_events)
            features['click_duration_variance'] = MouseProcessor.calculate_click_variance(click_events)
        
        # Pause and hesitation patterns
        features['pause_frequency'] = MouseProcessor.calculate_pause_frequency(move_events)
        features['micro_movement_ratio'] = MouseProcessor.calculate_micro_movements(move_events)
        
        # Behavioral rhythm
        features['movement_rhythm'] = MouseProcessor.calculate_movement_rhythm(move_events)
        features['acceleration_pattern'] = MouseProcessor.calculate_acceleration_pattern(velocities)
        
        return features
    
    @staticmethod
    def calculate_skewness(data: List[float]) -> float:
        """Calculate skewness of data distribution"""
        if len(data) < 3:
            return 0.0
        
        mean = np.mean(data)
        std = np.std(data)
        if std == 0:
            return 0.0
        
        skewness = np.mean([((x - mean) / std) ** 3 for x in data])
        return skewness
    
    @staticmethod
    def calculate_kurtosis(data: List[float]) -> float:
        """Calculate kurtosis of data distribution"""
        if len(data) < 4:
            return 0.0
        
        mean = np.mean(data)
        std = np.std(data)
        if std == 0:
            return 0.0
        
        kurtosis = np.mean([((x - mean) / std) ** 4 for x in data]) - 3
        return kurtosis
    
    @staticmethod
    def calculate_path_efficiency(move_events: List[Dict]) -> float:
        """Calculate how direct the mouse path is"""
        if len(move_events) < 2:
            return 1.0
        
        # Calculate total path length
        total_distance = sum(e.get('distance', 0) for e in move_events)
        
        # Calculate direct distance from start to end
        start_pos = (move_events[0]['x'], move_events[0]['y'])
        end_pos = (move_events[-1]['x'], move_events[-1]['y'])
        direct_distance = np.sqrt((end_pos[0] - start_pos[0])**2 + (end_pos[1] - start_pos[1])**2)
        
        if total_distance == 0:
            return 1.0
        
        return direct_distance / total_distance
    
    @staticmethod
    def calculate_movement_smoothness(move_events: List[Dict]) -> float:
        """Calculate smoothness of mouse movement"""
        if len(move_events) < 3:
            return 1.0
        
        velocities = [e.get('velocity', 0) for e in move_events]
        
        # Calculate velocity changes (jerk)
        jerk_values = []
        for i in range(1, len(velocities)):
            jerk = abs(velocities[i] - velocities[i-1])
            jerk_values.append(jerk)
        
        if not jerk_values:
            return 1.0
        
        # Lower jerk = smoother movement
        avg_jerk = np.mean(jerk_values)
        smoothness = 1.0 / (1.0 + avg_jerk)
        return smoothness
    
    @staticmethod
    def calculate_direction_consistency(move_events: List[Dict]) -> float:
        """Calculate consistency in movement direction"""
        directions = [e.get('direction', 0) for e in move_events if 'direction' in e]
        
        if len(directions) < 2:
            return 1.0
        
        # Calculate direction changes
        direction_changes = 0
        for i in range(1, len(directions)):
            angle_diff = abs(directions[i] - directions[i-1])
            # Normalize angle difference to 0-180 range
            angle_diff = min(angle_diff, 360 - angle_diff)
            if angle_diff > 45:  # Significant direction change
                direction_changes += 1
        
        consistency = 1.0 - (direction_changes / len(directions))
        return max(0.0, consistency)
    
    @staticmethod
    def calculate_click_precision(click_events: List[Dict]) -> float:
        """Calculate precision of mouse clicks"""
        if len(click_events) < 2:
            return 1.0
        
        # Calculate variance in click positions for similar targets
        click_positions = [(e['x'], e['y']) for e in click_events]
        
        # Simple precision metric based on position clustering
        total_variance = 0
        for i in range(len(click_positions)):
            for j in range(i+1, len(click_positions)):
                distance = np.sqrt((click_positions[i][0] - click_positions[j][0])**2 + 
                                 (click_positions[i][1] - click_positions[j][1])**2)
                total_variance += distance
        
        avg_variance = total_variance / (len(click_positions) * (len(click_positions) - 1) / 2)
        precision = 1.0 / (1.0 + avg_variance / 100)  # Normalize
        return precision
    
    @staticmethod
    def calculate_double_click_rate(click_events: List[Dict]) -> float:
        """Calculate rate of double clicks"""
        if len(click_events) < 2:
            return 0.0
        
        double_clicks = 0
        for i in range(1, len(click_events)):
            time_diff = click_events[i]['timestamp'] - click_events[i-1]['timestamp']
            if time_diff < 500:  # Within 500ms = potential double click
                double_clicks += 1
        
        return double_clicks / len(click_events)
    
    @staticmethod
    def calculate_click_variance(click_events: List[Dict]) -> float:
        """Calculate variance in click timing"""
        if len(click_events) < 2:
            return 0.0
        
        intervals = []
        for i in range(1, len(click_events)):
            interval = click_events[i]['timestamp'] - click_events[i-1]['timestamp']
            intervals.append(interval)
        
        return np.var(intervals) if intervals else 0.0
    
    @staticmethod
    def calculate_pause_frequency(move_events: List[Dict]) -> float:
        """Calculate frequency of movement pauses"""
        if len(move_events) < 5:
            return 0.0
        
        pauses = 0
        for event in move_events:
            if event.get('velocity', 0) < 0.1:  # Very slow = pause
                pauses += 1
        
        return pauses / len(move_events)
    
    @staticmethod
    def calculate_micro_movements(move_events: List[Dict]) -> float:
        """Calculate ratio of micro movements (very small distances)"""
        if not move_events:
            return 0.0
        
        micro_movements = sum(1 for e in move_events if e.get('distance', 0) < 5)
        return micro_movements / len(move_events)
    
    @staticmethod
    def calculate_movement_rhythm(move_events: List[Dict]) -> float:
        """Calculate rhythmic patterns in movement"""
        velocities = [e.get('velocity', 0) for e in move_events]
        
        if len(velocities) < 10:
            return 0.0
        
        # Simple rhythm detection using velocity autocorrelation
        rhythm_score = 0.0
        for lag in range(1, min(10, len(velocities)//2)):
            correlation = np.corrcoef(velocities[:-lag], velocities[lag:])[0, 1]
            if not np.isnan(correlation):
                rhythm_score += abs(correlation)
        
        return rhythm_score / 9  # Normalize by number of lags tested
    
    @staticmethod
    def calculate_acceleration_pattern(velocities: List[float]) -> float:
        """Calculate acceleration pattern consistency"""
        if len(velocities) < 3:
            return 0.0
        
        accelerations = []
        for i in range(1, len(velocities)):
            acceleration = velocities[i] - velocities[i-1]
            accelerations.append(acceleration)
        
        if not accelerations:
            return 0.0
        
        # Consistency measured as inverse of acceleration variance
        acc_variance = np.var(accelerations)
        consistency = 1.0 / (1.0 + acc_variance)
        return consistency

@router.post("/mouse")
async def process_mouse_data(
    data: MouseData,
    db: Session = Depends(get_db)
):
    """Process incoming mouse behavioral data"""
    try:
        # Get session from token
        session = DatabaseOperations.get_active_session(db, data.sessionToken)
        if not session:
            raise HTTPException(status_code=401, detail="Invalid session token")
        
        # Extract advanced features
        advanced_features = MouseProcessor.extract_advanced_features(data.rawData)
        
        # Combine with basic features
        all_features = {**data.features, **advanced_features}
        
        # Store behavioral event
        behavioral_event = BehavioralEvent(
            session_id=session.id,
            event_type="mouse",
            event_data=json.dumps(data.rawData),
            processed_features=json.dumps(all_features),
            timestamp=datetime.fromtimestamp(data.timestamp / 1000)
        )
        
        db.add(behavioral_event)
        db.commit()
        
        return {
            "status": "success",
            "message": f"Processed {len(data.rawData)} mouse events",
            "features_extracted": len(all_features),
            "event_id": behavioral_event.id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@router.get("/mouse/profile/{user_id}")
async def get_mouse_profile(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get mouse behavioral profile for a user"""
    try:
        # Get user's mouse behavioral events
        events = db.query(BehavioralEvent).join(
            BehavioralEvent.session
        ).filter(
            BehavioralEvent.event_type == "mouse",
            BehavioralEvent.session.has(user_id=user_id)
        ).limit(100).all()
        
        if not events:
            return {"profile": None, "message": "No mouse data available"}
        
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
        profile = MouseProcessor.calculate_profile_statistics(all_features)
        
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