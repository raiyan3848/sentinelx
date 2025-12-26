import logging
import sys
from datetime import datetime
from pathlib import Path

# Create logs directory if it doesn't exist
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Configure logging
def setup_logger(name: str = "SENTINELX", level: int = logging.INFO):
    """Setup logger with file and console handlers"""
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # File handler
    log_file = log_dir / f"sentinelx_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Create default logger
logger = setup_logger()

# Security event logger
security_logger = setup_logger("SENTINELX_SECURITY", logging.WARNING)

def log_security_event(event_type: str, user_id: int, details: dict):
    """Log security-related events"""
    security_logger.warning(f"SECURITY_EVENT: {event_type} - User: {user_id} - Details: {details}")

def log_trust_event(user_id: int, session_id: int, trust_score: float, action: str):
    """Log trust score events"""
    logger.info(f"TRUST_EVENT: User {user_id}, Session {session_id}, Score: {trust_score:.3f}, Action: {action}")

def log_behavioral_event(user_id: int, event_type: str, anomaly_score: float):
    """Log behavioral analysis events"""
    logger.info(f"BEHAVIORAL_EVENT: User {user_id}, Type: {event_type}, Anomaly Score: {anomaly_score:.3f}")

def log_ml_event(user_id: int, model_type: str, action: str, result: dict):
    """Log machine learning events"""
    logger.info(f"ML_EVENT: User {user_id}, Model: {model_type}, Action: {action}, Result: {result}")