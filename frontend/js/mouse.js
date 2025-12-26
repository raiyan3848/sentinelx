class MouseCollector {
    constructor() {
        this.mouseData = [];
        this.isCollecting = false;
        this.currentSession = null;
        this.lastMouseTime = null;
        this.lastPosition = { x: 0, y: 0 };
        
        // Mouse tracking parameters
        this.sampleRate = 50; // Collect every 50ms
        this.maxIdleTime = 5000; // 5 seconds of no movement
        
        this.init();
    }
    
    init() {
        // Mouse movement tracking
        document.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        document.addEventListener('click', (e) => this.handleClick(e));
        document.addEventListener('scroll', (e) => this.handleScroll(e));
        
        // Send data periodically
        setInterval(() => this.sendBatchData(), 4000);
    }
    
    startCollection(sessionToken) {
        this.currentSession = sessionToken;
        this.isCollecting = true;
        this.mouseData = [];
        console.log('🖱️ Mouse collection started');
    }
    
    stopCollection() {
        this.isCollecting = false;
        this.sendBatchData(); // Send remaining data
        console.log('⏹️ Mouse collection stopped');
    }
    
    handleMouseMove(event) {
        if (!this.isCollecting) return;
        
        const timestamp = performance.now();
        
        // Throttle data collection
        if (this.lastMouseTime && (timestamp - this.lastMouseTime) < this.sampleRate) {
            return;
        }
        
        const currentPos = {
            x: event.clientX,
            y: event.clientY
        };
        
        // Calculate movement metrics
        const distance = this.calculateDistance(this.lastPosition, currentPos);
        const timeDelta = this.lastMouseTime ? timestamp - this.lastMouseTime : 0;
        const velocity = timeDelta > 0 ? distance / timeDelta : 0;
        
        // Calculate direction
        const direction = this.calculateDirection(this.lastPosition, currentPos);
        
        const mouseEvent = {
            type: 'move',
            x: currentPos.x,
            y: currentPos.y,
            distance: distance,
            velocity: velocity,
            direction: direction,
            timestamp: Date.now(),
            timeDelta: timeDelta,
            sessionToken: this.currentSession
        };
        
        this.mouseData.push(mouseEvent);
        
        // Update tracking variables
        this.lastPosition = currentPos;
        this.lastMouseTime = timestamp;
    }
    
    handleClick(event) {
        if (!this.isCollecting) return;
        
        const clickEvent = {
            type: 'click',
            x: event.clientX,
            y: event.clientY,
            button: event.button, // 0=left, 1=middle, 2=right
            timestamp: Date.now(),
            target: event.target.tagName,
            sessionToken: this.currentSession
        };
        
        this.mouseData.push(clickEvent);
    }
    
    handleScroll(event) {
        if (!this.isCollecting) return;
        
        const scrollEvent = {
            type: 'scroll',
            deltaX: event.deltaX,
            deltaY: event.deltaY,
            timestamp: Date.now(),
            sessionToken: this.currentSession
        };
        
        this.mouseData.push(scrollEvent);
    }
    
    calculateDistance(pos1, pos2) {
        const dx = pos2.x - pos1.x;
        const dy = pos2.y - pos1.y;
        return Math.sqrt(dx * dx + dy * dy);
    }
    
    calculateDirection(pos1, pos2) {
        const dx = pos2.x - pos1.x;
        const dy = pos2.y - pos1.y;
        return Math.atan2(dy, dx) * (180 / Math.PI); // Convert to degrees
    }
    
    calculateFeatures(mouseEvents) {
        if (mouseEvents.length < 10) return null;
        
        const moveEvents = mouseEvents.filter(e => e.type === 'move');
        const clickEvents = mouseEvents.filter(e => e.type === 'click');
        
        if (moveEvents.length < 5) return null;
        
        const velocities = moveEvents.map(e => e.velocity).filter(v => v > 0);
        const distances = moveEvents.map(e => e.distance).filter(d => d > 0);
        const directions = moveEvents.map(e => e.direction);
        
        // Calculate pause patterns
        const pauses = this.calculatePauses(moveEvents);
        
        return {
            avgVelocity: this.average(velocities),
            stdVelocity: this.standardDeviation(velocities),
            avgDistance: this.average(distances),
            maxVelocity: Math.max(...velocities),
            minVelocity: Math.min(...velocities),
            totalDistance: distances.reduce((a, b) => a + b, 0),
            clickFrequency: clickEvents.length / (moveEvents.length || 1),
            pauseCount: pauses.length,
            avgPauseDuration: pauses.length > 0 ? this.average(pauses) : 0,
            directionChanges: this.calculateDirectionChanges(directions),
            movementSmoothness: this.calculateSmoothness(velocities)
        };
    }
    
    calculatePauses(moveEvents) {
        const pauses = [];
        let pauseStart = null;
        
        for (let i = 0; i < moveEvents.length; i++) {
            const event = moveEvents[i];
            
            if (event.velocity < 0.1) { // Very slow movement = pause
                if (!pauseStart) {
                    pauseStart = event.timestamp;
                }
            } else {
                if (pauseStart) {
                    const pauseDuration = event.timestamp - pauseStart;
                    if (pauseDuration > 100) { // Only count pauses > 100ms
                        pauses.push(pauseDuration);
                    }
                    pauseStart = null;
                }
            }
        }
        
        return pauses;
    }
    
    calculateDirectionChanges(directions) {
        let changes = 0;
        for (let i = 1; i < directions.length; i++) {
            const angleDiff = Math.abs(directions[i] - directions[i-1]);
            if (angleDiff > 45) { // Significant direction change
                changes++;
            }
        }
        return changes;
    }
    
    calculateSmoothness(velocities) {
        if (velocities.length < 2) return 0;
        
        let smoothness = 0;
        for (let i = 1; i < velocities.length; i++) {
            smoothness += Math.abs(velocities[i] - velocities[i-1]);
        }
        return smoothness / velocities.length;
    }
    
    async sendBatchData() {
        if (this.mouseData.length === 0) return;
        
        const features = this.calculateFeatures(this.mouseData);
        if (!features) return;
        
        const payload = {
            eventType: 'mouse',
            rawData: this.mouseData,
            features: features,
            sessionToken: this.currentSession,
            timestamp: Date.now()
        };
        
        try {
            const response = await fetch('/api/behavior/mouse', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                },
                body: JSON.stringify(payload)
            });
            
            if (response.ok) {
                console.log(`🖱️ Sent ${this.mouseData.length} mouse events`);
                this.mouseData = []; // Clear sent data
            }
        } catch (error) {
            console.error('❌ Failed to send mouse data:', error);
        }
    }
    
    // Utility functions
    average(arr) {
        return arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
    }
    
    standardDeviation(arr) {
        if (arr.length === 0) return 0;
        const avg = this.average(arr);
        const squareDiffs = arr.map(value => Math.pow(value - avg, 2));
        return Math.sqrt(this.average(squareDiffs));
    }
}

// Global mouse collector instance
window.mouseCollector = new MouseCollector();