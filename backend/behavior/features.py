import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.decomposition import PCA
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..database.models import BehavioralEvent, UserSession

class FeatureEngineer:
    """
    Advanced feature engineering for behavioral biometric authentication
    Transforms raw keystroke and mouse data into ML-ready features
    """
    
    def __init__(self):
        self.keystroke_scaler = StandardScaler()
        self.mouse_scaler = StandardScaler()
        self.pca_keystroke = PCA(n_components=10)
        self.pca_mouse = PCA(n_components=15)
        self.is_fitted = False
    
    def extract_session_features(self, db: Session, session_id: int) -> Dict[str, float]:
        """Extract comprehensive features for a user session"""
        
        # Get all behavioral events for this session
        events = db.query(BehavioralEvent).filter(
            BehavioralEvent.session_id == session_id
        ).order_by(BehavioralEvent.timestamp).all()
        
        if not events:
            return {}
        
        # Separate keystroke and mouse events
        keystroke_events = [e for e in events if e.event_type == "keystroke"]
        mouse_events = [e for e in events if e.event_type == "mouse"]
        
        features = {}
        
        # Extract keystroke features
        if keystroke_events:
            keystroke_features = self.extract_keystroke_features(keystroke_events)
            features.update(keystroke_features)
        
        # Extract mouse features
        if mouse_events:
            mouse_features = self.extract_mouse_features(mouse_events)
            features.update(mouse_features)
        
        # Extract temporal features
        temporal_features = self.extract_temporal_features(events)
        features.update(temporal_features)
        
        # Extract cross-modal features
        if keystroke_events and mouse_events:
            cross_features = self.extract_cross_modal_features(keystroke_events, mouse_events)
            features.update(cross_features)
        
        return features
    
    def extract_keystroke_features(self, events: List[BehavioralEvent]) -> Dict[str, float]:
        """Extract advanced keystroke dynamics features"""
        features = {}
        
        # Aggregate all processed features
        all_features = []
        for event in events:
            try:
                event_features = json.loads(event.processed_features)
                all_features.append(event_features)
            except:
                continue
        
        if not all_features:
            return {}
        
        # Statistical aggregation of features
        feature_names = set()
        for f in all_features:
            feature_names.update(f.keys())
        
        for feature_name in feature_names:
            values = [f.get(feature_name, 0) for f in all_features if feature_name in f]
            if values:
                features[f"ks_{feature_name}_mean"] = np.mean(values)
                features[f"ks_{feature_name}_std"] = np.std(values)
                features[f"ks_{feature_name}_median"] = np.median(values)
                features[f"ks_{feature_name}_iqr"] = np.percentile(values, 75) - np.percentile(values, 25)
        
        # Advanced keystroke patterns
        features.update(self._extract_keystroke_patterns(all_features))
        
        return features
    
    def extract_mouse_features(self, events: List[BehavioralEvent]) -> Dict[str, float]:
        """Extract advanced mouse behavioral features"""
        features = {}
        
        # Aggregate all processed features
        all_features = []
        for event in events:
            try:
                event_features = json.loads(event.processed_features)
                all_features.append(event_features)
            except:
                continue
        
        if not all_features:
            return {}
        
        # Statistical aggregation of features
        feature_names = set()
        for f in all_features:
            feature_names.update(f.keys())
        
        for feature_name in feature_names:
            values = [f.get(feature_name, 0) for f in all_features if feature_name in f]
            if values:
                features[f"ms_{feature_name}_mean"] = np.mean(values)
                features[f"ms_{feature_name}_std"] = np.std(values)
                features[f"ms_{feature_name}_median"] = np.median(values)
                features[f"ms_{feature_name}_max"] = np.max(values)
                features[f"ms_{feature_name}_min"] = np.min(values)
        
        # Advanced mouse patterns
        features.update(self._extract_mouse_patterns(all_features))
        
        return features
    
    def extract_temporal_features(self, events: List[BehavioralEvent]) -> Dict[str, float]:
        """Extract temporal behavioral patterns"""
        features = {}
        
        if len(events) < 2:
            return features
        
        # Event timing patterns
        timestamps = [event.timestamp for event in events]
        time_diffs = [(timestamps[i] - timestamps[i-1]).total_seconds() 
                     for i in range(1, len(timestamps))]
        
        if time_diffs:
            features["temporal_avg_interval"] = np.mean(time_diffs)
            features["temporal_std_interval"] = np.std(time_diffs)
            features["temporal_max_gap"] = np.max(time_diffs)
            features["temporal_activity_bursts"] = sum(1 for diff in time_diffs if diff < 0.5)
        
        # Session activity patterns
        session_duration = (timestamps[-1] - timestamps[0]).total_seconds()
        features["temporal_session_duration"] = session_duration
        features["temporal_event_rate"] = len(events) / session_duration if session_duration > 0 else 0
        
        # Activity distribution over time
        features.update(self._extract_activity_distribution(timestamps))
        
        return features
    
    def extract_cross_modal_features(self, keystroke_events: List[BehavioralEvent], 
                                   mouse_events: List[BehavioralEvent]) -> Dict[str, float]:
        """Extract features that combine keystroke and mouse behavior"""
        features = {}
        
        # Synchronization patterns
        ks_times = [e.timestamp for e in keystroke_events]
        ms_times = [e.timestamp for e in mouse_events]
        
        # Calculate interaction patterns
        features["cross_ks_ms_ratio"] = len(keystroke_events) / len(mouse_events) if mouse_events else 0
        
        # Temporal correlation between typing and mouse movement
        correlation = self._calculate_temporal_correlation(ks_times, ms_times)
        features["cross_temporal_correlation"] = correlation
        
        # Multitasking patterns
        features.update(self._extract_multitasking_patterns(keystroke_events, mouse_events))
        
        return features
    
    def _extract_keystroke_patterns(self, features_list: List[Dict]) -> Dict[str, float]:
        """Extract advanced keystroke behavioral patterns"""
        patterns = {}
        
        # Typing consistency over time
        if len(features_list) > 1:
            dwell_means = [f.get('avg_dwell_time', 0) for f in features_list]
            flight_means = [f.get('avg_flight_time', 0) for f in features_list]
            
            patterns["ks_dwell_consistency"] = 1.0 / (1.0 + np.std(dwell_means)) if dwell_means else 0
            patterns["ks_flight_consistency"] = 1.0 / (1.0 + np.std(flight_means)) if flight_means else 0
        
        # Typing rhythm stability
        rhythm_vars = [f.get('typing_rhythm_variance', 0) for f in features_list]
        patterns["ks_rhythm_stability"] = 1.0 / (1.0 + np.mean(rhythm_vars)) if rhythm_vars else 0
        
        # Error pattern analysis
        error_rates = [f.get('error_correction_rate', 0) for f in features_list]
        patterns["ks_error_consistency"] = 1.0 - np.std(error_rates) if error_rates else 0
        
        return patterns
    
    def _extract_mouse_patterns(self, features_list: List[Dict]) -> Dict[str, float]:
        """Extract advanced mouse behavioral patterns"""
        patterns = {}
        
        # Movement consistency
        if len(features_list) > 1:
            velocity_means = [f.get('velocity_mean', 0) for f in features_list]
            smoothness_vals = [f.get('movement_smoothness', 0) for f in features_list]
            
            patterns["ms_velocity_consistency"] = 1.0 / (1.0 + np.std(velocity_means)) if velocity_means else 0
            patterns["ms_smoothness_consistency"] = 1.0 / (1.0 + np.std(smoothness_vals)) if smoothness_vals else 0
        
        # Click pattern stability
        click_precisions = [f.get('click_precision', 0) for f in features_list]
        patterns["ms_click_stability"] = 1.0 - np.std(click_precisions) if click_precisions else 0
        
        # Movement efficiency trends
        path_effs = [f.get('path_efficiency', 0) for f in features_list]
        patterns["ms_efficiency_trend"] = np.mean(path_effs) if path_effs else 0
        
        return patterns
    
    def _extract_activity_distribution(self, timestamps: List[datetime]) -> Dict[str, float]:
        """Extract activity distribution patterns over time"""
        features = {}
        
        if len(timestamps) < 10:
            return features
        
        # Convert to relative time (seconds from start)
        start_time = timestamps[0]
        relative_times = [(t - start_time).total_seconds() for t in timestamps]
        
        # Divide session into time bins and analyze activity
        session_duration = relative_times[-1]
        if session_duration > 0:
            num_bins = min(10, int(session_duration / 30))  # 30-second bins, max 10 bins
            if num_bins > 1:
                bin_size = session_duration / num_bins
                bin_counts = [0] * num_bins
                
                for time in relative_times:
                    bin_idx = min(int(time / bin_size), num_bins - 1)
                    bin_counts[bin_idx] += 1
                
                # Activity distribution metrics
                features["activity_uniformity"] = 1.0 - (np.std(bin_counts) / np.mean(bin_counts)) if np.mean(bin_counts) > 0 else 0
                features["activity_peak_ratio"] = np.max(bin_counts) / np.mean(bin_counts) if np.mean(bin_counts) > 0 else 0
        
        return features
    
    def _calculate_temporal_correlation(self, ks_times: List[datetime], 
                                      ms_times: List[datetime]) -> float:
        """Calculate temporal correlation between keystroke and mouse events"""
        if len(ks_times) < 5 or len(ms_times) < 5:
            return 0.0
        
        # Create time series with 1-second resolution
        all_times = sorted(ks_times + ms_times)
        start_time = all_times[0]
        end_time = all_times[-1]
        duration = (end_time - start_time).total_seconds()
        
        if duration < 10:  # Need at least 10 seconds
            return 0.0
        
        # Create binary time series
        time_bins = int(duration)
        ks_series = [0] * time_bins
        ms_series = [0] * time_bins
        
        for t in ks_times:
            bin_idx = min(int((t - start_time).total_seconds()), time_bins - 1)
            ks_series[bin_idx] = 1
        
        for t in ms_times:
            bin_idx = min(int((t - start_time).total_seconds()), time_bins - 1)
            ms_series[bin_idx] = 1
        
        # Calculate correlation
        correlation = np.corrcoef(ks_series, ms_series)[0, 1]
        return correlation if not np.isnan(correlation) else 0.0
    
    def _extract_multitasking_patterns(self, ks_events: List[BehavioralEvent], 
                                     ms_events: List[BehavioralEvent]) -> Dict[str, float]:
        """Extract multitasking behavioral patterns"""
        features = {}
        
        # Combine and sort all events by timestamp
        all_events = [(e.timestamp, 'ks') for e in ks_events] + [(e.timestamp, 'ms') for e in ms_events]
        all_events.sort()
        
        if len(all_events) < 10:
            return features
        
        # Analyze switching patterns
        switches = 0
        current_mode = all_events[0][1]
        
        for _, event_type in all_events[1:]:
            if event_type != current_mode:
                switches += 1
                current_mode = event_type
        
        features["multitask_switch_rate"] = switches / len(all_events)
        
        # Analyze mode persistence (how long user stays in one mode)
        mode_durations = []
        current_start = all_events[0][0]
        current_mode = all_events[0][1]
        
        for timestamp, event_type in all_events[1:]:
            if event_type != current_mode:
                duration = (timestamp - current_start).total_seconds()
                mode_durations.append(duration)
                current_start = timestamp
                current_mode = event_type
        
        if mode_durations:
            features["multitask_avg_persistence"] = np.mean(mode_durations)
            features["multitask_persistence_variance"] = np.var(mode_durations)
        
        return features
    
    def create_feature_vector(self, features_dict: Dict[str, float]) -> np.ndarray:
        """Convert feature dictionary to standardized vector"""
        # Define expected feature order (this should be consistent across all users)
        expected_features = self._get_expected_feature_names()
        
        # Create vector with default values
        vector = []
        for feature_name in expected_features:
            value = features_dict.get(feature_name, 0.0)
            # Handle NaN and infinite values
            if np.isnan(value) or np.isinf(value):
                value = 0.0
            vector.append(value)
        
        return np.array(vector)
    
    def _get_expected_feature_names(self) -> List[str]:
        """Get list of expected feature names in consistent order"""
        # This should include all possible features that can be extracted
        # In a real implementation, this would be learned from training data
        base_features = [
            # Keystroke features
            "ks_avg_dwell_time_mean", "ks_avg_dwell_time_std", "ks_avg_flight_time_mean",
            "ks_typing_rhythm_variance_mean", "ks_pressure_consistency_mean",
            "ks_dwell_consistency", "ks_flight_consistency", "ks_rhythm_stability",
            
            # Mouse features  
            "ms_velocity_mean_mean", "ms_velocity_mean_std", "ms_path_efficiency_mean",
            "ms_movement_smoothness_mean", "ms_click_precision_mean",
            "ms_velocity_consistency", "ms_smoothness_consistency",
            
            # Temporal features
            "temporal_avg_interval", "temporal_std_interval", "temporal_event_rate",
            "activity_uniformity", "activity_peak_ratio",
            
            # Cross-modal features
            "cross_ks_ms_ratio", "cross_temporal_correlation", "multitask_switch_rate"
        ]
        
        return base_features
    
    def fit_scalers(self, feature_vectors: List[np.ndarray]):
        """Fit scalers on training data"""
        if not feature_vectors:
            return
        
        # Combine all feature vectors
        X = np.vstack(feature_vectors)
        
        # Fit scalers
        self.keystroke_scaler.fit(X[:, :20])  # First 20 features are keystroke
        self.mouse_scaler.fit(X[:, 20:40])    # Next 20 are mouse
        
        # Fit PCA for dimensionality reduction
        self.pca_keystroke.fit(X[:, :20])
        self.pca_mouse.fit(X[:, 20:40])
        
        self.is_fitted = True
    
    def transform_features(self, feature_vector: np.ndarray) -> np.ndarray:
        """Transform features using fitted scalers"""
        if not self.is_fitted:
            return feature_vector
        
        # Split features
        ks_features = feature_vector[:20]
        ms_features = feature_vector[20:40]
        other_features = feature_vector[40:]
        
        # Scale features
        ks_scaled = self.keystroke_scaler.transform(ks_features.reshape(1, -1))[0]
        ms_scaled = self.mouse_scaler.transform(ms_features.reshape(1, -1))[0]
        
        # Apply PCA
        ks_pca = self.pca_keystroke.transform(ks_scaled.reshape(1, -1))[0]
        ms_pca = self.pca_mouse.transform(ms_scaled.reshape(1, -1))[0]
        
        # Combine transformed features
        transformed = np.concatenate([ks_pca, ms_pca, other_features])
        
        return transformed