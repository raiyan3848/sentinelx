#!/usr/bin/env python3
"""
SENTINELX System Test Script
Tests basic functionality of the behavioral biometric authentication system
"""

import sys
import requests
import time
import json
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent / "backend"))

def test_database():
    """Test database initialization"""
    try:
        from backend.database.db import init_database, SessionLocal
        from backend.database.models import User
        
        print("🗄️ Testing database initialization...")
        init_database()
        
        # Test database connection
        db = SessionLocal()
        users = db.query(User).count()
        db.close()
        
        print(f"✅ Database initialized successfully. Users: {users}")
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_auth_service():
    """Test authentication service"""
    try:
        from backend.auth.login import AuthService
        from backend.database.db import SessionLocal
        
        print("🔐 Testing authentication service...")
        
        # Test password hashing
        password = "test123"
        hashed = AuthService.get_password_hash(password)
        verified = AuthService.verify_password(password, hashed)
        
        if not verified:
            raise Exception("Password verification failed")
        
        print("✅ Authentication service working correctly")
        return True
    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        return False

def test_ml_components():
    """Test ML components"""
    try:
        from backend.behavior.features import FeatureEngineer
        from backend.ml.train_model import BehavioralAnomalyDetector
        
        print("🤖 Testing ML components...")
        
        # Test feature engineer
        feature_engineer = FeatureEngineer()
        
        # Test anomaly detector
        detector = BehavioralAnomalyDetector()
        
        print("✅ ML components initialized successfully")
        return True
    except Exception as e:
        print(f"❌ ML components test failed: {e}")
        return False

def test_trust_engine():
    """Test trust engine"""
    try:
        from backend.trust.trust_engine import TrustEngine, TrustLevel, SecurityAction
        
        print("🛡️ Testing trust engine...")
        
        # Test trust engine initialization
        trust_engine = TrustEngine()
        
        # Test trust level enum
        levels = list(TrustLevel)
        actions = list(SecurityAction)
        
        print(f"✅ Trust engine initialized. Levels: {len(levels)}, Actions: {len(actions)}")
        return True
    except Exception as e:
        print(f"❌ Trust engine test failed: {e}")
        return False

def test_api_server():
    """Test API server (requires server to be running)"""
    try:
        print("🌐 Testing API server...")
        
        # Test health endpoint
        response = requests.get("http://localhost:8000/api/health", timeout=5)
        
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ API server healthy: {health_data}")
            return True
        else:
            print(f"❌ API server returned status: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠️ API server not running. Start with ./run.sh or run.bat")
        return False
    except Exception as e:
        print(f"❌ API server test failed: {e}")
        return False

def test_frontend_files():
    """Test frontend files exist"""
    try:
        print("🎨 Testing frontend files...")
        
        frontend_files = [
            "frontend/index.html",
            "frontend/login.html", 
            "frontend/dashboard.html",
            "frontend/css/style.css",
            "frontend/js/api.js",
            "frontend/js/keystroke.js",
            "frontend/js/mouse.js",
            "frontend/js/trust_score.js"
        ]
        
        missing_files = []
        for file_path in frontend_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            print(f"❌ Missing frontend files: {missing_files}")
            return False
        
        print("✅ All frontend files present")
        return True
    except Exception as e:
        print(f"❌ Frontend files test failed: {e}")
        return False

def run_all_tests():
    """Run all system tests"""
    print("🚀 SENTINELX System Test Suite")
    print("=" * 50)
    
    tests = [
        ("Database", test_database),
        ("Authentication", test_auth_service),
        ("ML Components", test_ml_components),
        ("Trust Engine", test_trust_engine),
        ("Frontend Files", test_frontend_files),
        ("API Server", test_api_server),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name} test...")
        result = test_func()
        results.append((test_name, result))
        time.sleep(0.5)  # Brief pause between tests
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:15} {status}")
        if result:
            passed += 1
    
    print(f"\nTests passed: {passed}/{len(tests)}")
    
    if passed == len(tests):
        print("\n🎉 All tests passed! SENTINELX is ready to use.")
        print("\n🚀 Next steps:")
        print("1. Run './run.sh' (Linux/Mac) or 'run.bat' (Windows)")
        print("2. Visit http://localhost:8000")
        print("3. Create an account and test the system")
    else:
        print(f"\n⚠️ {len(tests) - passed} tests failed. Please check the errors above.")
    
    return passed == len(tests)

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)