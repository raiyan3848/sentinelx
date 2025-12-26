/**
 * SENTINELX API Client
 * Handles all API communications with the backend
 */

class SentinelXAPI {
    constructor() {
        this.baseURL = '/api';
        this.accessToken = localStorage.getItem('access_token');
        this.sessionToken = localStorage.getItem('session_token');
    }

    /**
     * Set authentication tokens
     */
    setTokens(accessToken, sessionToken) {
        this.accessToken = accessToken;
        this.sessionToken = sessionToken;
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('session_token', sessionToken);
    }

    /**
     * Clear authentication tokens
     */
    clearTokens() {
        this.accessToken = null;
        this.sessionToken = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('session_token');
    }

    /**
     * Get default headers for API requests
     */
    getHeaders() {
        const headers = {
            'Content-Type': 'application/json'
        };

        if (this.accessToken) {
            headers['Authorization'] = `Bearer ${this.accessToken}`;
        }

        return headers;
    }

    /**
     * Make API request with error handling
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        
        const config = {
            headers: this.getHeaders(),
            ...options
        };

        try {
            const response = await fetch(url, config);
            
            // Handle authentication errors
            if (response.status === 401) {
                this.clearTokens();
                window.location.href = '/login.html';
                throw new Error('Authentication required');
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || `HTTP ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error(`API request failed: ${endpoint}`, error);
            throw error;
        }
    }

    // Authentication APIs
    async login(username, password) {
        return this.request('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
    }

    async register(username, email, password) {
        return this.request('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ username, email, password })
        });
    }

    async getCurrentUser() {
        return this.request('/auth/me');
    }

    async logout() {
        try {
            await this.request('/auth/logout', { method: 'POST' });
        } finally {
            this.clearTokens();
        }
    }

    // Behavioral Data APIs
    async sendKeystrokeData(data) {
        return this.request('/behavior/keystroke', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async sendMouseData(data) {
        return this.request('/behavior/mouse', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async getBehavioralProfile(userId) {
        return this.request(`/behavior/profile/${userId}`);
    }

    // Trust Score APIs
    async getTrustScore(sessionToken = null) {
        const token = sessionToken || this.sessionToken;
        return this.request('/trust/score', {
            method: 'POST',
            body: JSON.stringify({ sessionToken: token })
        });
    }

    async getTrustHistory(userId, days = 7) {
        return this.request(`/trust/history/${userId}?days=${days}`);
    }

    // ML Model APIs
    async getModelStatus(userId) {
        return this.request(`/ml/model/status/${userId}`);
    }

    async trainUserModel(userId) {
        return this.request(`/ml/model/train/${userId}`, {
            method: 'POST'
        });
    }

    // Session Management APIs
    async getSessionInfo(sessionId) {
        return this.request(`/session/${sessionId}`);
    }

    async updateSessionActivity() {
        if (!this.sessionToken) return;
        
        return this.request('/session/activity', {
            method: 'PUT',
            body: JSON.stringify({ sessionToken: this.sessionToken })
        });
    }

    // Security Action APIs
    async executeSecurityAction(sessionId, action) {
        return this.request('/security/action', {
            method: 'POST',
            body: JSON.stringify({ sessionId, action })
        });
    }

    async getSecurityAlerts(userId) {
        return this.request(`/security/alerts/${userId}`);
    }

    // Analytics APIs
    async getBehavioralAnalytics(userId, timeRange = '24h') {
        return this.request(`/analytics/behavioral/${userId}?range=${timeRange}`);
    }

    async getSystemMetrics() {
        return this.request('/analytics/system');
    }

    // Real-time WebSocket connection
    connectWebSocket() {
        if (!this.sessionToken) {
            console.warn('No session token available for WebSocket connection');
            return null;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${this.sessionToken}`;
        
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            console.log('🔗 WebSocket connected');
        };
        
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error);
            }
        };
        
        ws.onclose = () => {
            console.log('🔌 WebSocket disconnected');
            // Attempt to reconnect after 5 seconds
            setTimeout(() => {
                if (this.sessionToken) {
                    this.connectWebSocket();
                }
            }, 5000);
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
        
        return ws;
    }

    handleWebSocketMessage(data) {
        // Dispatch custom events for different message types
        switch (data.type) {
            case 'trust_update':
                window.dispatchEvent(new CustomEvent('trustScoreUpdate', { detail: data }));
                break;
            case 'security_alert':
                window.dispatchEvent(new CustomEvent('securityAlert', { detail: data }));
                break;
            case 'behavioral_anomaly':
                window.dispatchEvent(new CustomEvent('behavioralAnomaly', { detail: data }));
                break;
            default:
                console.log('Unknown WebSocket message type:', data.type);
        }
    }

    // Utility methods
    isAuthenticated() {
        return !!(this.accessToken && this.sessionToken);
    }

    getSessionToken() {
        return this.sessionToken;
    }

    getAccessToken() {
        return this.accessToken;
    }

    // Health check
    async healthCheck() {
        try {
            const response = await fetch('/api/health');
            return response.ok;
        } catch (error) {
            return false;
        }
    }
}

// Global API instance
window.sentinelAPI = new SentinelXAPI();

// Auto-refresh tokens before expiry (if needed)
setInterval(async () => {
    if (window.sentinelAPI.isAuthenticated()) {
        try {
            // Update session activity to keep it alive
            await window.sentinelAPI.updateSessionActivity();
        } catch (error) {
            console.warn('Failed to update session activity:', error);
        }
    }
}, 5 * 60 * 1000); // Every 5 minutes

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SentinelXAPI;
}