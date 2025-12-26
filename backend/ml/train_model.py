import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import json
from typing import Dict, List, Tuple, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..database.db import get_db, SessionLocal
from ..database.models import User, BehavioralEvent, BehavioralProfile
from ..behavior.features import FeatureEngineer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BehavioralAnomalyDetector:
    """
    Advanced ML pipeline for behavioral biometric anomaly detection
    Uses ensemble of algorithms for robust authentication
    """
    
    def __init__(self):
        # Ensemble of anomaly detection models
        self.models = {
            'isolation_forest': IsolationForest(
                contamination=0.1,
                random_state=42,
                n_estimators=100
            ),
            'one_class_svm': OneClassSVM(
                kernel='rbf',
                gamma='scale',
                nu=0.1
            ),
            'local_outlier_factor': LocalOutlierFactor(
                n_neighbors=20,
                contamination=0.1,
                novelty=True
            )
        }
        
        self.feature_engineer = FeatureEngineer()
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_importance = {}
        
        # Model performance metrics
        self.model_weights = {
            'isolation_forest': 0.4,
            'one_class_svm': 0.3,
            'local_outlier_factor': 0.3
        }
    
    def collect_training_data(self, db: Session, user_id: int, 
                            days_back: int = 30) -> Tuple[np.ndarray, List[Dict]]:
        """Collect and prepare training data for a specific user"""
        
        # Get user's behavioral events from the last N days
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        events = db.query(BehavioralEvent).join(
            BehavioralEvent.session
        ).filter(
            BehavioralEvent.session.has(user_id=user_id),
            BehavioralEvent.timestamp >= cutoff_date
        ).order_by(BehavioralEvent.timestamp).all()
        
        if len(events) < 50:  # Need minimum samples for training
            logger.warning(f"Insufficient training data for user {user_id}: {len(events)} events")
            return np.array([]), []
        
        # Group events by session for feature extraction
        session_groups = {}
        for event in events:
            session_id = event.session_id
            if session_id not in session_groups:
                session_groups[session_id] = []
            session_groups[session_id].append(event)
        
        # Extract features for each session
        feature_vectors = []
        feature_dicts = []
        
        for session_id, session_events in session_groups.items():
            if len(session_events) >= 10:  # Minimum events per session
                features = self.feature_engineer.extract_session_features(db, session_id)
                if features:
                    feature_vector = self.feature_engineer.create_feature_vector(features)
                    feature_vectors.append(feature_vector)
                    feature_dicts.append(features)
        
        if len(feature_vectors) < 10:
            logger.warning(f"Insufficient feature vectors for user {user_id}: {len(feature_vectors)}")
            return np.array([]), []
        
        return np.array(feature_vectors), feature_dicts
    
    def train_user_model(self, user_id: int, db: Session = None) -> Dict[str, Any]:
        """Train anomaly detection model for a specific user"""
        
        if db is None:
            db = SessionLocal()
        
        try:
            logger.info(f"Training model for user {user_id}")
            
            # Collect training data
            X_train, feature_dicts = self.collect_training_data(db, user_id)
            
            if len(X_train) == 0:
                return {
                    "success": False,
                    "message": "Insufficient training data",
                    "samples_collected": 0
                }
            
            # Fit feature scalers
            self.feature_engineer.fit_scalers([X_train])
            
            # Transform features
            X_scaled = self.scaler.fit_transform(X_train)
            
            # Train ensemble models
            trained_models = {}
            model_scores = {}
            
            for model_name, model in self.models.items():
                try:
                    logger.info(f"Training {model_name}")
                    
                    if model_name == 'local_outlier_factor':
                        # LOF requires special handling for novelty detection
                        model.fit(X_scaled)
                    else:
                        model.fit(X_scaled)
                    
                    # Evaluate model on training data
                    if model_name != 'local_outlier_factor':
                        predictions = model.predict(X_scaled)
                        anomaly_scores = model.decision_function(X_scaled)
                    else:
                        predictions = model.predict(X_scaled)
                        anomaly_scores = model.negative_outlier_factor_
                    
                    # Calculate model performance metrics
                    normal_ratio = np.sum(predictions == 1) / len(predictions)
                    score_variance = np.var(anomaly_scores)
                    
                    trained_models[model_name] = model
                    model_scores[model_name] = {
                        'normal_ratio': normal_ratio,
                        'score_variance': score_variance,
                        'mean_score': np.mean(anomaly_scores)
                    }
                    
                    logger.info(f"{model_name} trained successfully - Normal ratio: {normal_ratio:.3f}")
                    
                except Exception as e:
                    logger.error(f"Failed to train {model_name}: {str(e)}")
                    continue
            
            if not trained_models:
                return {
                    "success": False,
                    "message": "All models failed to train",
                    "samples_collected": len(X_train)
                }
            
            # Calculate feature importance
            self.feature_importance = self._calculate_feature_importance(X_scaled, feature_dicts)
            
            # Save models and metadata
            model_data = {
                'models': trained_models,
                'scaler': self.scaler,
                'feature_engineer': self.feature_engineer,
                'model_scores': model_scores,
                'feature_importance': self.feature_importance,
                'training_samples': len(X_train),
                'trained_at': datetime.utcnow().isoformat()
            }
            
            # Save to file
            model_filename = f"user_{user_id}_model.pkl"
            joblib.dump(model_data, model_filename)
            
            # Update user's behavioral profile
            self._update_behavioral_profile(db, user_id, feature_dicts, model_scores)
            
            self.is_trained = True
            
            return {
                "success": True,
                "message": "Model trained successfully",
                "samples_collected": len(X_train),
                "models_trained": list(trained_models.keys()),
                "model_file": model_filename,
                "feature_importance": dict(list(self.feature_importance.items())[:10])  # Top 10
            }
            
        except Exception as e:
            logger.error(f"Training failed for user {user_id}: {str(e)}")
            return {
                "success": False,
                "message": f"Training failed: {str(e)}",
                "samples_collected": 0
            }
        finally:
            db.close()
    
    def _calculate_feature_importance(self, X: np.ndarray, 
                                    feature_dicts: List[Dict]) -> Dict[str, float]:
        """Calculate feature importance using variance and correlation analysis"""
        
        if len(X) == 0:
            return {}
        
        feature_names = self.feature_engineer._get_expected_feature_names()
        importance_scores = {}
        
        # Calculate variance-based importance
        feature_variances = np.var(X, axis=0)
        
        # Normalize variances
        max_variance = np.max(feature_variances) if np.max(feature_variances) > 0 else 1
        normalized_variances = feature_variances / max_variance
        
        for i, feature_name in enumerate(feature_names[:len(normalized_variances)]):
            importance_scores[feature_name] = float(normalized_variances[i])
        
        # Sort by importance
        sorted_importance = dict(sorted(importance_scores.items(), 
                                      key=lambda x: x[1], reverse=True))
        
        return sorted_importance
    
    def _update_behavioral_profile(self, db: Session, user_id: int, 
                                 feature_dicts: List[Dict], model_scores: Dict):
        """Update user's behavioral profile in database"""
        
        # Calculate aggregate statistics
        all_features = {}
        for feature_dict in feature_dicts:
            for key, value in feature_dict.items():
                if key not in all_features:
                    all_features[key] = []
                all_features[key].append(value)
        
        # Calculate profile statistics
        profile_stats = {}
        for feature, values in all_features.items():
            profile_stats[f"{feature}_mean"] = np.mean(values)
            profile_stats[f"{feature}_std"] = np.std(values)
        
        # Check if profile exists
        profile = db.query(BehavioralProfile).filter(
            BehavioralProfile.user_id == user_id
        ).first()
        
        if profile:
            # Update existing profile
            profile.samples_count = len(feature_dicts)
            profile.confidence_score = min(len(feature_dicts) / 100.0, 1.0)  # Max confidence at 100 samples
            profile.last_updated = datetime.utcnow()
            
            # Update keystroke and mouse patterns
            keystroke_features = {k: v for k, v in profile_stats.items() if k.startswith('ks_')}
            mouse_features = {k: v for k, v in profile_stats.items() if k.startswith('ms_')}
            
            if keystroke_features:
                profile.typing_rhythm_pattern = json.dumps(keystroke_features)
            if mouse_features:
                profile.mouse_movement_pattern = json.dumps(mouse_features)
        else:
            # Create new profile
            profile = BehavioralProfile(
                user_id=user_id,
                samples_count=len(feature_dicts),
                confidence_score=min(len(feature_dicts) / 100.0, 1.0),
                typing_rhythm_pattern=json.dumps({k: v for k, v in profile_stats.items() if k.startswith('ks_')}),
                mouse_movement_pattern=json.dumps({k: v for k, v in profile_stats.items() if k.startswith('ms_')}),
                last_updated=datetime.utcnow()
            )
            db.add(profile)
        
        db.commit()
        logger.info(f"Updated behavioral profile for user {user_id}")
    
    def train_all_users(self, db: Session = None) -> Dict[str, Any]:
        """Train models for all users with sufficient data"""
        
        if db is None:
            db = SessionLocal()
        
        try:
            # Get all users
            users = db.query(User).all()
            
            results = {
                "total_users": len(users),
                "trained_successfully": 0,
                "training_failed": 0,
                "insufficient_data": 0,
                "details": []
            }
            
            for user in users:
                logger.info(f"Processing user {user.id}: {user.username}")
                
                result = self.train_user_model(user.id, db)
                results["details"].append({
                    "user_id": user.id,
                    "username": user.username,
                    "result": result
                })
                
                if result["success"]:
                    results["trained_successfully"] += 1
                elif result["samples_collected"] == 0:
                    results["insufficient_data"] += 1
                else:
                    results["training_failed"] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Batch training failed: {str(e)}")
            return {
                "success": False,
                "message": f"Batch training failed: {str(e)}"
            }
        finally:
            db.close()

def main():
    """Main training function"""
    logger.info("Starting SENTINELX model training")
    
    detector = BehavioralAnomalyDetector()
    
    # Train models for all users
    results = detector.train_all_users()
    
    logger.info("Training completed")
    logger.info(f"Results: {results}")
    
    return results

if __name__ == "__main__":
    main()