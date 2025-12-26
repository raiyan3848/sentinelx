/**
 * SENTINELX Trust Score Manager
 * Handles real-time trust score updates and visualizations
 */

class TrustScoreManager {
    constructor() {
        this.currentTrustScore = 0;
        this.trustHistory = [];
        this.updateInterval = null;
        this.isMonitoring = false;
        
        // Trust level thresholds
        this.trustLevels = {
            CRITICAL: { min: 0.0, max: 0.2, color: '#ff6b6b', label: 'Critical' },
            LOW: { min: 0.2, max: 0.4, color: '#ff9f43', label: 'Low' },
            MODERATE: { min: 0.4, max: 0.6, color: '#ffeb3b', label: 'Moderate' },
            HIGH: { min: 0.6, max: 0.8, color: '#00d4ff', label: 'High' },
            MAXIMUM: { min: 0.8, max: 1.0, color: '#00ff88', label: 'Maximum' }
        };
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.createTrustIndicators();
    }
    
    setupEventListeners() {
        // Listen for trust score updates from WebSocket
        window.addEventListener('trustScoreUpdate', (event) => {
            this.handleTrustUpdate(event.detail);
        });
        
        // Listen for security alerts
        window.addEventListener('securityAlert', (event) => {
            this.handleSecurityAlert(event.detail);
        });
        
        // Listen for behavioral anomalies
        window.addEventListener('behavioralAnomaly', (event) => {
            this.handleBehavioralAnomaly(event.detail);
        });
    }
    
    createTrustIndicators() {
        // Create trust indicators on pages that don't have them
        if (!document.getElementById('trustScore')) {
            this.createFloatingTrustIndicator();
        }
    }
    
    createFloatingTrustIndicator() {
        const indicator = document.createElement('div');
        indicator.id = 'floatingTrustIndicator';
        indicator.className = 'floating-trust-indicator';
        indicator.innerHTML = `
            <div class="trust-mini-gauge">
                <div class="trust-mini-fill" id="trustMiniFill"></div>
            </div>
            <div class="trust-mini-info">
                <span class="trust-mini-score" id="trustMiniScore">--</span>
                <span class="trust-mini-level" id="trustMiniLevel">--</span>
            </div>
        `;
        
        document.body.appendChild(indicator);
        
        // Add CSS for floating indicator
        this.addFloatingIndicatorStyles();
    }
    
    addFloatingIndicatorStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .floating-trust-indicator {
                position: fixed;
                top: 20px;
                right: 20px;
                background: rgba(26, 26, 46, 0.95);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 0.75rem;
                padding: 1rem;
                display: flex;
                align-items: center;
                gap: 1rem;
                z-index: 1000;
                min-width: 150px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            }
            
            .trust-mini-gauge {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: conic-gradient(from 0deg, #ff6b6b 0deg, #ffeb3b 120deg, #00ff88 240deg);
                display: flex;
                align-items: center;
                justify-content: center;
                position: relative;
            }
            
            .trust-mini-gauge::before {
                content: '';
                position: absolute;
                width: 28px;
                height: 28px;
                border-radius: 50%;
                background: #1a1a2e;
            }
            
            .trust-mini-fill {
                position: absolute;
                width: 32px;
                height: 32px;
                border-radius: 50%;
                background: conic-gradient(from 0deg, var(--trust-color, #00ff88) 0deg, transparent 0deg);
                z-index: 1;
            }
            
            .trust-mini-info {
                display: flex;
                flex-direction: column;
                gap: 0.25rem;
            }
            
            .trust-mini-score {
                font-size: 1.1rem;
                font-weight: bold;
                color: #ffffff;
            }
            
            .trust-mini-level {
                font-size: 0.7rem;
                text-transform: uppercase;
                color: var(--trust-color, #00ff88);
                font-weight: 600;
            }
        `;
        document.head.appendChild(style);
    }
    
    startMonitoring(sessionToken) {
        if (this.isMonitoring) return;
        
        this.isMonitoring = true;
        this.sessionToken = sessionToken;
        
        // Initial trust score fetch
        this.updateTrustScore();
        
        // Set up periodic updates
        this.updateInterval = setInterval(() => {
            this.updateTrustScore();
        }, 10000); // Update every 10 seconds
        
        console.log('🛡️ Trust score monitoring started');
    }
    
    stopMonitoring() {
        this.isMonitoring = false;
        
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        
        console.log('⏹️ Trust score monitoring stopped');
    }
    
    async updateTrustScore() {
        if (!this.sessionToken) return;
        
        try {
            const trustData = await window.sentinelAPI.getTrustScore(this.sessionToken);
            this.handleTrustUpdate(trustData);
        } catch (error) {
            console.error('Failed to update trust score:', error);
        }
    }
    
    handleTrustUpdate(trustData) {
        const score = trustData.trust_score || 0;
        const level = trustData.trust_level || 'unknown';
        
        this.currentTrustScore = score;
        this.trustHistory.push({
            score: score,
            level: level,
            timestamp: new Date(),
            components: trustData.trust_components || {}
        });
        
        // Keep only last 100 entries
        if (this.trustHistory.length > 100) {
            this.trustHistory.shift();
        }
        
        // Update UI elements
        this.updateTrustDisplay(score, level, trustData);
        
        // Check for critical trust levels
        if (level === 'critical' || level === 'low') {
            this.handleLowTrust(trustData);
        }
        
        // Trigger custom event for other components
        window.dispatchEvent(new CustomEvent('trustScoreChanged', {
            detail: { score, level, data: trustData }
        }));
    }
    
    updateTrustDisplay(score, level, trustData) {
        const percentage = Math.round(score * 100);
        const trustLevel = this.getTrustLevelInfo(level);
        
        // Update main trust score elements
        const elements = {
            trustScore: document.getElementById('trustScore'),
            trustLevel: document.getElementById('trustLevel'),
            trustPercentage: document.getElementById('trustPercentage'),
            trustGauge: document.getElementById('trustGauge'),
            
            // Mini indicator elements
            trustMiniScore: document.getElementById('trustMiniScore'),
            trustMiniLevel: document.getElementById('trustMiniLevel'),
            trustMiniFill: document.getElementById('trustMiniFill')
        };
        
        // Update text elements
        if (elements.trustScore) elements.trustScore.textContent = percentage;
        if (elements.trustLevel) elements.trustLevel.textContent = trustLevel.label.toUpperCase();
        if (elements.trustPercentage) elements.trustPercentage.textContent = percentage;
        if (elements.trustMiniScore) elements.trustMiniScore.textContent = percentage;
        if (elements.trustMiniLevel) elements.trustMiniLevel.textContent = trustLevel.label;
        
        // Update gauge elements
        if (elements.trustGauge) {
            elements.trustGauge.style.width = percentage + '%';
            elements.trustGauge.className = `gauge-fill trust-${level.replace('_', '-')}`;
        }
        
        if (elements.trustMiniFill) {
            const angle = (percentage / 100) * 360;
            elements.trustMiniFill.style.background = 
                `conic-gradient(from 0deg, ${trustLevel.color} ${angle}deg, transparent ${angle}deg)`;
        }
        
        // Update CSS custom properties for color theming
        document.documentElement.style.setProperty('--trust-color', trustLevel.color);
        
        // Update component scores if available
        this.updateComponentScores(trustData.trust_components || {});
    }
    
    updateComponentScores(components) {
        const componentElements = {
            behavioralScore: document.getElementById('behavioralScore'),
            temporalScore: document.getElementById('temporalScore'),
            contextScore: document.getElementById('contextScore'),
            historicalScore: document.getElementById('historicalScore'),
            anomalyScore: document.getElementById('anomalyScore')
        };
        
        const componentMapping = {
            behavioralScore: 'behavioral_score',
            temporalScore: 'temporal_consistency',
            contextScore: 'session_context',
            historicalScore: 'historical_trust',
            anomalyScore: 'anomaly_frequency'
        };
        
        Object.entries(componentElements).forEach(([elementId, element]) => {
            if (element && componentMapping[elementId]) {
                const value = components[componentMapping[elementId]] || 0;
                element.textContent = Math.round(value * 100);
            }
        });
    }
    
    getTrustLevelInfo(level) {
        const levelKey = level.toUpperCase().replace('-', '_');
        return this.trustLevels[levelKey] || this.trustLevels.MODERATE;
    }
    
    handleLowTrust(trustData) {
        const level = trustData.trust_level;
        const score = Math.round(trustData.trust_score * 100);
        
        // Show notification
        this.showTrustNotification(
            `Trust level: ${level.toUpperCase()} (${score}%)`,
            level === 'critical' ? 'error' : 'warning'
        );
        
        // Log the event
        console.warn(`🚨 Low trust detected: ${level} (${score}%)`);
        
        // Execute recommended security action
        if (trustData.recommended_action && trustData.recommended_action !== 'no_action') {
            this.handleSecurityAction(trustData.recommended_action, trustData);
        }
    }
    
    handleSecurityAlert(alertData) {
        this.showTrustNotification(
            alertData.message || 'Security alert detected',
            alertData.severity || 'warning'
        );
    }
    
    handleBehavioralAnomaly(anomalyData) {
        const message = `Behavioral anomaly detected: ${anomalyData.type || 'Unknown'}`;
        this.showTrustNotification(message, 'info');
    }
    
    handleSecurityAction(action, trustData) {
        switch (action) {
            case 'terminate_session':
                this.showTrustNotification(
                    'Session will be terminated due to security concerns',
                    'error'
                );
                setTimeout(() => {
                    window.location.href = '/login.html';
                }, 5000);
                break;
                
            case 'require_reauth':
                this.showTrustNotification(
                    'Re-authentication required',
                    'warning'
                );
                // Could trigger re-auth modal here
                break;
                
            case 'restrict_access':
                this.showTrustNotification(
                    'Access restrictions have been applied',
                    'warning'
                );
                break;
                
            case 'increase_monitoring':
                this.showTrustNotification(
                    'Security monitoring increased',
                    'info'
                );
                break;
        }
    }
    
    showTrustNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `trust-notification trust-notification-${type}`;
        notification.innerHTML = `
            <div class="notification-icon">
                ${type === 'error' ? '🚨' : type === 'warning' ? '⚠️' : 'ℹ️'}
            </div>
            <div class="notification-message">${message}</div>
            <button class="notification-close">×</button>
        `;
        
        // Add styles if not already added
        this.addNotificationStyles();
        
        // Add to page
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
        
        // Close button functionality
        notification.querySelector('.notification-close').addEventListener('click', () => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        });
    }
    
    addNotificationStyles() {
        if (document.getElementById('trustNotificationStyles')) return;
        
        const style = document.createElement('style');
        style.id = 'trustNotificationStyles';
        style.textContent = `
            .trust-notification {
                position: fixed;
                top: 80px;
                right: 20px;
                background: rgba(26, 26, 46, 0.95);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 0.5rem;
                padding: 1rem;
                display: flex;
                align-items: center;
                gap: 1rem;
                z-index: 1001;
                max-width: 300px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
                animation: slideIn 0.3s ease-out;
            }
            
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            
            .trust-notification-error {
                border-left: 4px solid #ff6b6b;
            }
            
            .trust-notification-warning {
                border-left: 4px solid #ffeb3b;
            }
            
            .trust-notification-info {
                border-left: 4px solid #00d4ff;
            }
            
            .notification-icon {
                font-size: 1.2rem;
            }
            
            .notification-message {
                flex: 1;
                color: #ffffff;
                font-size: 0.9rem;
            }
            
            .notification-close {
                background: none;
                border: none;
                color: #888;
                font-size: 1.2rem;
                cursor: pointer;
                padding: 0;
                width: 20px;
                height: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .notification-close:hover {
                color: #ffffff;
            }
        `;
        document.head.appendChild(style);
    }
    
    // Utility methods
    getCurrentTrustScore() {
        return this.currentTrustScore;
    }
    
    getTrustHistory() {
        return [...this.trustHistory];
    }
    
    getTrustTrend() {
        if (this.trustHistory.length < 2) return 'stable';
        
        const recent = this.trustHistory.slice(-5);
        const trend = recent[recent.length - 1].score - recent[0].score;
        
        if (Math.abs(trend) < 0.05) return 'stable';
        return trend > 0 ? 'increasing' : 'decreasing';
    }
}

// Global trust score manager instance
window.trustScoreManager = new TrustScoreManager();

// Auto-start monitoring when session is available
document.addEventListener('DOMContentLoaded', () => {
    const sessionToken = localStorage.getItem('session_token');
    if (sessionToken && window.trustScoreManager) {
        window.trustScoreManager.startMonitoring(sessionToken);
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TrustScoreManager;
}