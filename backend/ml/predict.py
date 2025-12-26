import numpy as np
import joblib
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging
from sqlalchemy.orm import Session
from ..database.db import get_db
from ..database.models import BehavioralEvent, UserSession
from ..behavior.features import FeatureEngineer
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealTimePredictor:
    """
    Real-time behavioral anomaly prediction system
    Analyzes live user behavior and calculates anomaly scores
    """
    
    def __init__(self):
        self.loaded_models = {}  # Cache for loaded user models
        self.feature_engineer = FeatureEngineer()
        
        # Anomaly thresholds
        self.thresholds = {
            'low_risk': 0.3,      # Minor anomaly
            'medium_risk': 0.6,   # Moderate anomaly
            'high_risk': 0.8      # Severe anomaly
        }
        
        # Ensemble weights for different models
        self.model_weights = {
            'isolation_forest': 0.4,
            'one_class_svm': 0.3,
            'local_outlier_factor': 0.3
        }
    
    def load_user_model(self, user_id: int) -> bool:
        """Load trained model for a specific user"""
        
        if user_id in self.loaded_models:
            return True
        
        try:
            model_filename = f"user_{user_id}_model.pkl"
            model_data = joblib.load(model_filename)
            
            self.loaded_models[user_id] = {
                'models': model_data['models'],
                'scaler': model_data['scaler'],
                'feature_engineer': model_data['feature_engineer'],
                'model_scores': model_data['model_scores'],
                'feature_importance': model_data['feature_importance'],
                'loaded_at': datetime.utcnow()
            }
            
            logger.info(f"Loaded model for user {user_id}")
            return True
            
        except FileNotFoundError:
            logger.warning(f"No trained model found for user {user_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to load model for user {user_id}: {str(e)}")
            return False
    
    def predict_anomaly(self, user_id: int, session_id: int, 
                       db: Session) -> Dict[str, any]:
        """Predict anomaly for current user session"""
        
        # Load user model if not already loaded
        if not self.load_user_model(user_id):
            return {
                "anomaly_score": 0.0,
                "risk_level": "unknown",
                "confidence": 0.0,
                "message": "No trained model available"
            }
        
        try:
            # Extract features for current session
            features = self.feature_engineer.extract_session_features(db, session_id)
            
            if not features:
                return {
                    "anomaly_score": 0.0,
                    "risk_level": "insufficient_data",
                    "confidence": 0.0,
                    "message": "Insufficient behavioral data"
                }
            
            # Convert to feature vector
            feature_vector = self.feature_engineer.create_feature_vector(features)
            
            # Get user's trained models
            user_models = self.loaded_models[user_id]
            scaler = user_models['scaler']
            models = user_models['models']
            
            # Scale features
            X_scaled = scaler.transform(feature_vector.reshape(1, -1))
            
            # Get predictions from ensemble
            ensemble_scores = {}
            ensemble_predictions = {}
            
            for model_name, model in models.items():
                try:
                    if model_name == 'local_outlier_factor':
                        # LOF returns negative outlier factor
                        score = model.decision_function(X_scaled)[0]
                        prediction = model.predict(X_scaled)[0]
                    else:
                        score = model.decision_function(X_scaled)[0]
                        prediction = model.predict(X_scaled)[0]
                    
                    ensemble_scores[model_name] = score
                    ensemble_predictions[model_name] = prediction
                    
                except Exception as e:
                    logger.warning(f"Model {model_name} prediction failed: {str(e)}")
                    continue
            
            if not ensemble_scores:
                return {
                    "anomaly_score": 0.0,
                    "risk_level": "error",
                    "confidence": 0.0,
                    "message": "All models failed to predict"
                }
            
            # Calculate weighted ensemble score
            weighted_score = 0.0
            total_weight = 0.0
            
            for model_name, score in ensemble_scores.items():
                weight = self.model_weights.get(model_name, 0.33)
                
                # Normalize scores to 0-1 range (anomaly probability)
                normalized_score = self._normalize_anomaly_score(score, model_name)
                
                weighted_score += normalized_score * weight
                total_weight += weight
            
            if total_weight > 0:
                final_anomaly_score = weighted_score / total_weight
            else:
                final_anomaly_score = 0.0
            
            # Determine risk level
            risk_level = self._determine_risk_level(final_anomaly_score)
            
            # Calculate confidence based on model agreement
            confidence = self._calculate_confidence(ensemble_scores, ensemble_predictions)
            
            # Feature analysis for explainability
            feature_analysis = self._analyze_anomalous_features(
                features, user_models['feature_importance']
            )
            
            result = {
                "anomaly_score": float(final_anomaly_score),
                "risk_level": risk_level,
                "confidence": float(confidence),
                "model_scores": {k: float(v) for k, v in ensemble_scores.items()},
                "feature_analysis": feature_analysis,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Log high-risk predictions
            if risk_level in ['medium_risk', 'high_risk']:
                logger.warning(f"Anomaly detected for user {user_id}: {risk_level} "
                             f"(score: {final_anomaly_score:.3f})")
            
            return result
            
        except Exception as e:
            logger.error(f"Prediction failed for user {user_id}: {str(e)}")
            return {
                "anomaly_score": 0.0,
                "risk_level": "error",
                "confidence": 0.0,
                "message": f"Prediction error: {str(e)}"
            }
    
    def _normalize_anomaly_score(self, score: float, model_name: str) -> float:
        """Normalize model-specific scores to 0-1 anomaly probability"""
        
        if model_name == 'isolation_forest':
            # Isolation Forest: negative scores = anomalies
            # Typical range: -0.5 to 0.5
            normalized = max(0, (0.5 - score) / 1.0)
        
        elif model_name == 'one_class_svm':
            # One-Class SVM: negative scores = anomalies
            # Typical range: -2 to 2
            normalized = max(0, (2 - score) / 4.0)
        
        elif model_name == 'local_outlier_factor':
            # LOF: more negative = more anomalous
            # Typical range: -3 to -1
            normalized = max(0, min(1, (-score - 1) / 2.0))
        
        else:
            # Default normalization
            normalized = max(0, min(1, (1 - score) / 2.0))
        
        return min(1.0, max(0.0, normalized))
    
    def _determine_risk_level(self, anomaly_score: float) -> str:
        """Determine risk level based on anomaly score"""
        
        if anomaly_score >= self.thresholds['high_risk']:
            return 'high_risk'
        elif anomaly_score >= self.thresholds['medium_risk']:
            return 'medium_risk'
        elif anomaly_score >= self.thresholds['low_risk']:
            return 'low_risk'
        else:
            return 'normal'
    
    def _calculate_confidence(self, scores: Dict[str, float], 
                            predictions: Dict[str, int]) -> float:
        """Calculate prediction confidence based on model agreement"""
        
        if len(scores) < 2:
            return 0.5  # Low confidence with single model
        
        # Check prediction agreement
        pred_values = list(predictions.values())
        agreement_ratio = pred_values.count(pred_values[0]) / len(pred_values)
        
        # Check score consistency (lower variance = higher confidence)
        score_values = list(scores.values())
        score_variance = np.var(score_values)
        consistency = 1.0 / (1.0 + score_variance)
        
        # Combine agreement and consistency
        confidence = (agreement_ratio * 0.6) + (consistency * 0.4)
        
        return min(1.0, max(0.0, confidence))
    
    def _analyze_anomalous_features(self, current_features: Dict[str, float],
                                  feature_importance: Dict[str, float]) -> Dict[str, any]:
        """Analyze which features contribute most to anomaly detection"""
        
        # Get top important features
        top_features = dict(list(feature_importance.items())[:10])
        
        anomalous_features = []
        for feature_name, importance in top_features.items():
            if feature_name in current_features:
                value = current_features[feature_name]
                
                # Simple anomaly detection for individual features
                # In practice, this would use learned thresholds
                if abs(value) > 2.0:  # Simple z-score threshold
                    anomalous_features.append({
                        "feature": feature_name,
                        "value": float(value),
                        "importance": float(importance),
                        "anomaly_type": "extreme_value"
                    })
        
        return {
            "anomalous_features": anomalous_features,
            "total_features_analyzed": len(current_features),
            "top_important_features": list(top_features.keys())[:5]
        }
    
    def batch_predict(self, user_id: int, session_ids: List[int], 
                     db: Session) -> List[Dict[str, any]]:
        """Predict anomalies for multiple sessions"""
        
        results = []
        for session_id in session_ids:
            result = self.predict_anomaly(user_id, session_id, db)
            result['session_id'] = session_id
            results.append(result)
        
        return results
    
    def get_model_status(self, user_id: int) -> Dict[str, any]:
        """Get status of loaded model for user"""
        
        if user_id not in self.loaded_models:
            return {
                "loaded": False,
                "message": "Model not loaded"
            }
        
        model_info = self.loaded_models[user_id]
        
        return {
            "loaded": True,
            "models_available": list(model_info['models'].keys()),
            "loaded_at": model_info['loaded_at'].isoformat(),
            "feature_count": len(model_info['feature_importance']),
            "top_features": list(model_info['feature_importance'].keys())[:5]
        }
    
    def clear_model_cache(self, user_id: Optional[int] = None):
        """Clear model cache for specific user or all users"""
        
        if user_id:
            if user_id in self.loaded_models:
                del self.loaded_models[user_id]
                logger.info(f"Cleared model cache for user {user_id}")
        else:
            self.loaded_models.clear()
            logger.info("Cleared all model caches")

# Global predictor instance
predictor = RealTimePredictor()