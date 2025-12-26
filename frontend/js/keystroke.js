class KeystrokeCollector {
    constructor() {
        this.keystrokeData = [];
        this.isCollecting = false;
        this.lastKeyTime = null;
        this.currentSession = null;
        
        // Keystroke timing thresholds
        this.maxFlightTime = 2000; // Max 2 seconds between keys
        this.minDwellTime = 10;    // Min 10ms key press
        
        this.init();
    }
    
    init() {
        // Start collecting when user begins typing
        document.addEventListener('keydown', (e) => this.handleKeyDown(e));
        document.addEventListener('keyup', (e) => this.handleKeyUp(e));
        
        // Send data periodically
        setInterval(() => this.sendBatchData(), 3000);
    }
    
    startCollection(sessionToken) {
        this.currentSession = sessionToken;
        this.isCollecting = true;
        this.keystrokeData = [];
        console.log('🎯 Keystroke collection started');
    }
    
    stopCollection() {
        this.isCollecting = false;
        this.sendBatchData(); // Send remaining data
        console.log('⏹️ Keystroke collection stopped');
    }
    
    handleKeyDown(event) {
        if (!this.isCollecting) return;
        
        const timestamp = performance.now();
        const keyCode = event.code;
        
        // Calculate flight time (time between keys)
        let flightTime = null;
        if (this.lastKeyTime) {
            flightTime = timestamp - this.lastKeyTime;
        }
        
        // Store key press start
        this.currentKeyPress = {
            keyCode: keyCode,
            keyDownTime: timestamp,
            flightTime: flightTime,
            isSpecialKey: this.isSpecialKey(event)
        };
        
        this.lastKeyTime = timestamp;
    }
    
    handleKeyUp(event) {
        if (!this.isCollecting || !this.currentKeyPress) return;
        
        const timestamp = performance.now();
        const keyCode = event.code;
        
        // Only process if it's the same key
        if (this.currentKeyPress.keyCode === keyCode) {
            const dwellTime = timestamp - this.currentKeyPress.keyDownTime;
            
            // Create keystroke event
            const keystrokeEvent = {
                keyCode: keyCode,
                dwellTime: dwellTime,
                flightTime: this.currentKeyPress.flightTime,
                timestamp: Date.now(),
                isSpecialKey: this.currentKeyPress.isSpecialKey,
                sessionToken: this.currentSession
            };
            
            // Validate and store
            if (this.isValidKeystroke(keystrokeEvent)) {
                this.keystrokeData.push(keystrokeEvent);
            }
            
            this.currentKeyPress = null;
        }
    }
    
    isSpecialKey(event) {
        const specialKeys = [
            'Backspace', 'Delete', 'Enter', 'Tab', 'Escape',
            'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight',
            'Shift', 'Control', 'Alt', 'Meta'
        ];
        return specialKeys.includes(event.code);
    }
    
    isValidKeystroke(keystroke) {
        // Filter out invalid keystrokes
        if (keystroke.dwellTime < this.minDwellTime) return false;
        if (keystroke.flightTime && keystroke.flightTime > this.maxFlightTime) return false;
        return true;
    }
    
    calculateFeatures(keystrokes) {
        if (keystrokes.length < 5) return null;
        
        const dwellTimes = keystrokes.map(k => k.dwellTime);
        const flightTimes = keystrokes.filter(k => k.flightTime).map(k => k.flightTime);
        
        return {
            avgDwellTime: this.average(dwellTimes),
            stdDwellTime: this.standardDeviation(dwellTimes),
            avgFlightTime: this.average(flightTimes),
            stdFlightTime: this.standardDeviation(flightTimes),
            typingSpeed: keystrokes.length / ((keystrokes[keystrokes.length - 1].timestamp - keystrokes[0].timestamp) / 1000),
            specialKeyRatio: keystrokes.filter(k => k.isSpecialKey).length / keystrokes.length
        };
    }
    
    async sendBatchData() {
        if (this.keystrokeData.length === 0) return;
        
        const features = this.calculateFeatures(this.keystrokeData);
        if (!features) return;
        
        const payload = {
            eventType: 'keystroke',
            rawData: this.keystrokeData,
            features: features,
            sessionToken: this.currentSession,
            timestamp: Date.now()
        };
        
        try {
            const response = await fetch('/api/behavior/keystroke', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                },
                body: JSON.stringify(payload)
            });
            
            if (response.ok) {
                console.log(`📊 Sent ${this.keystrokeData.length} keystroke events`);
                this.keystrokeData = []; // Clear sent data
            }
        } catch (error) {
            console.error('❌ Failed to send keystroke data:', error);
        }
    }
    
    // Utility functions
    average(arr) {
        return arr.reduce((a, b) => a + b, 0) / arr.length;
    }
    
    standardDeviation(arr) {
        const avg = this.average(arr);
        const squareDiffs = arr.map(value => Math.pow(value - avg, 2));
        return Math.sqrt(this.average(squareDiffs));
    }
}

// Global keystroke collector instance
window.keystrokeCollector = new KeystrokeCollector();