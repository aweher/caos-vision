/**
 * WebSocket client with automatic reconnection, health checking, and event handling.
 */
class WebSocketClient {
    constructor(path) {
        this.path = path;
        this.ws = null;
        this.listeners = new Map();
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.baseReconnectDelay = 1000;
        this.pingInterval = null;
        this.pongTimeout = null;
        this.isConnecting = false;
        this.lastPongTime = null;
        this.connectionHealthy = false;
        this.pingTimeoutMs = 10000; // 10 seconds to receive pong

        this.connect();
    }

    connect() {
        if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
            return;
        }

        this.isConnecting = true;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${window.location.host}${this.path}`;

        console.log(`WebSocket connecting to ${url}...`);

        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.isConnecting = false;
            this.reconnectAttempts = 0;
            this.connectionHealthy = true;
            this.lastPongTime = Date.now();
            this.emit('connect');
            this.emit('health_change', { healthy: true });
            this.startPing();
        };

        this.ws.onclose = (event) => {
            console.log(`WebSocket closed: ${event.code} ${event.reason}`);
            this.isConnecting = false;
            this.stopPing();
            if (this.connectionHealthy) {
                this.connectionHealthy = false;
                this.emit('health_change', { healthy: false, reason: 'disconnected' });
            }
            this.emit('disconnect', { code: event.code, reason: event.reason });

            // Don't reconnect for auth errors
            if (event.code === 4001) {
                console.log('Authentication required, not reconnecting');
                return;
            }

            this.scheduleReconnect();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.isConnecting = false;
            this.emit('error', error);
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                // Handle ping/pong
                if (data.type === 'ping') {
                    this.send({ type: 'pong' });
                    return;
                }

                if (data.type === 'pong') {
                    this.handlePong();
                    return;
                }

                this.emit(data.type, data);
            } catch (e) {
                console.error('Failed to parse WebSocket message:', e);
            }
        };
    }

    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnect attempts reached');
            this.emit('max_reconnect_attempts');
            return;
        }

        // Exponential backoff with jitter
        const delay = Math.min(
            this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts) + Math.random() * 1000,
            30000
        );
        this.reconnectAttempts++;

        console.log(`Reconnecting in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts})`);
        setTimeout(() => this.connect(), delay);
    }

    startPing() {
        this.stopPing();
        this.pingInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.send({ type: 'ping' });
                this.startPongTimeout();
            }
        }, 25000);
    }

    stopPing() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
        this.clearPongTimeout();
    }

    startPongTimeout() {
        this.clearPongTimeout();
        this.pongTimeout = setTimeout(() => {
            console.warn('Pong timeout - connection may be lost');
            if (this.connectionHealthy) {
                this.connectionHealthy = false;
                this.emit('health_change', { healthy: false, reason: 'pong_timeout' });
            }
            // Force reconnect
            if (this.ws) {
                this.ws.close();
            }
        }, this.pingTimeoutMs);
    }

    clearPongTimeout() {
        if (this.pongTimeout) {
            clearTimeout(this.pongTimeout);
            this.pongTimeout = null;
        }
    }

    handlePong() {
        this.lastPongTime = Date.now();
        this.clearPongTimeout();
        if (!this.connectionHealthy) {
            this.connectionHealthy = true;
            this.emit('health_change', { healthy: true });
        }
    }

    getLastPongTime() {
        return this.lastPongTime;
    }

    isHealthy() {
        return this.connectionHealthy && this.ws && this.ws.readyState === WebSocket.OPEN;
    }

    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }
        this.listeners.get(event).add(callback);
        return () => this.off(event, callback);
    }

    off(event, callback) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).delete(callback);
        }
    }

    emit(event, data) {
        if (this.listeners.has(event)) {
            for (const callback of this.listeners.get(event)) {
                try {
                    callback(data);
                } catch (e) {
                    console.error(`Error in ${event} listener:`, e);
                }
            }
        }
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
            return true;
        }
        return false;
    }

    close() {
        this.stopPing();
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// Export for use in other scripts
window.WebSocketClient = WebSocketClient;
