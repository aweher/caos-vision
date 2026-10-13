/**
 * Viewer page - displays video grid with real-time updates.
 */
class StreamViewer {
    constructor() {
        this.container = document.getElementById('grid-container');
        this.emptyState = document.getElementById('empty-state');
        this.statusEl = document.getElementById('connection-status');
        this.disconnectOverlay = document.getElementById('disconnect-overlay');
        this.players = new Map();

        // Spotlight state
        this.spotlightStreamId = null;
        this.savedLayout = null;

        // Connection monitoring
        this.healthCheckInterval = null;
        this.healthCheckIntervalMs = 15000; // Check every 15 seconds
        this.disconnectedSince = null;
        this.disconnectTimerInterval = null;

        this.ws = new WebSocketClient('/ws/viewer');
        this.setupEventHandlers();
        this.setupInteractions();
        this.startHealthCheck();
    }

    setupEventHandlers() {
        // Connection status
        this.ws.on('connect', () => this.handleConnect());
        this.ws.on('disconnect', () => this.handleDisconnect());
        this.ws.on('health_change', (data) => this.handleHealthChange(data));
        this.ws.on('max_reconnect_attempts', () => this.handleMaxReconnectAttempts());

        // Stream events
        this.ws.on('stream_update', (data) => this.handleFullUpdate(data));
        this.ws.on('stream_added', (data) => this.handleStreamAdded(data));
        this.ws.on('stream_removed', (data) => this.handleStreamRemoved(data));
        this.ws.on('stream_muted', (data) => this.handleMuteChange(data));

        // Admin commands
        this.ws.on('force_refresh', () => this.handleForceRefresh());
        this.ws.on('stream_spotlight', (data) => this.handleSpotlight(data));
    }

    handleConnect() {
        this.disconnectedSince = null;
        this.stopDisconnectTimer();
        this.updateConnectionStatus('connected');
        this.hideDisconnectOverlay();
    }

    handleDisconnect() {
        if (!this.disconnectedSince) {
            this.disconnectedSince = Date.now();
        }
        this.updateConnectionStatus('disconnected');
        this.showDisconnectOverlay();
        this.startDisconnectTimer();
    }

    handleHealthChange(data) {
        if (!data.healthy) {
            if (!this.disconnectedSince) {
                this.disconnectedSince = Date.now();
            }
            this.updateConnectionStatus('unhealthy');
            this.showDisconnectOverlay();
            this.startDisconnectTimer();
        } else {
            this.disconnectedSince = null;
            this.stopDisconnectTimer();
            this.updateConnectionStatus('connected');
            this.hideDisconnectOverlay();
        }
    }

    // HTTP Health Check - backup connectivity check
    startHealthCheck() {
        this.healthCheckInterval = setInterval(() => {
            this.performHealthCheck();
        }, this.healthCheckIntervalMs);
        // Also perform immediate check
        this.performHealthCheck();
    }

    async performHealthCheck() {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000);

            const response = await fetch('/api/v1/health', {
                method: 'GET',
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            if (response.ok) {
                // If WebSocket is down but HTTP is up, connection might be recovering
                if (!this.ws.isHealthy() && this.disconnectedSince) {
                    console.log('HTTP health check passed, WebSocket recovering...');
                }
            } else {
                this.handleHealthCheckFailure('Server returned error');
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                this.handleHealthCheckFailure('Health check timeout');
            } else {
                this.handleHealthCheckFailure(error.message);
            }
        }
    }

    handleHealthCheckFailure(reason) {
        console.warn('Health check failed:', reason);
        if (!this.disconnectedSince) {
            this.disconnectedSince = Date.now();
            this.showDisconnectOverlay();
            this.startDisconnectTimer();
        }
        this.updateConnectionStatus('unhealthy');
    }

    startDisconnectTimer() {
        this.stopDisconnectTimer();
        this.disconnectTimerInterval = setInterval(() => {
            this.updateDisconnectDuration();
        }, 1000);
    }

    stopDisconnectTimer() {
        if (this.disconnectTimerInterval) {
            clearInterval(this.disconnectTimerInterval);
            this.disconnectTimerInterval = null;
        }
    }

    updateDisconnectDuration() {
        if (!this.disconnectedSince) return;

        const duration = Math.floor((Date.now() - this.disconnectedSince) / 1000);
        const durationEl = document.getElementById('disconnect-duration');
        if (durationEl) {
            durationEl.textContent = this.formatDuration(duration);
        }
    }

    formatDuration(seconds) {
        if (seconds < 60) {
            return `${seconds}s`;
        } else if (seconds < 3600) {
            const mins = Math.floor(seconds / 60);
            const secs = seconds % 60;
            return `${mins}m ${secs}s`;
        } else {
            const hours = Math.floor(seconds / 3600);
            const mins = Math.floor((seconds % 3600) / 60);
            return `${hours}h ${mins}m`;
        }
    }

    showDisconnectOverlay() {
        if (this.disconnectOverlay) {
            this.disconnectOverlay.classList.remove('hidden');
        }
    }

    hideDisconnectOverlay() {
        if (this.disconnectOverlay) {
            this.disconnectOverlay.classList.add('hidden');
        }
    }

    handleForceRefresh() {
        console.log('Force refresh triggered by admin');
        window.location.reload();
    }

    setupInteractions() {
        // Delegate click events
        this.container.addEventListener('click', (e) => {
            const muteBtn = e.target.closest('.mute-btn');
            if (muteBtn) {
                e.preventDefault();
                this.handleLocalMuteToggle(muteBtn);
            }
        });

        // Double-click for fullscreen
        this.container.addEventListener('dblclick', (e) => {
            const wrapper = e.target.closest('.stream-wrapper');
            if (wrapper) {
                this.toggleFullscreen(wrapper);
            }
        });
    }

    updateConnectionStatus(status) {
        this.statusEl.className = `connection-status ${status}`;
        const textEl = this.statusEl.querySelector('.status-text');
        switch (status) {
            case 'connected':
                textEl.textContent = 'Connected';
                break;
            case 'disconnected':
                textEl.textContent = 'Disconnected - Reconnecting...';
                break;
            case 'unhealthy':
                textEl.textContent = 'Connection Lost';
                break;
            default:
                textEl.textContent = 'Connecting...';
        }
    }

    handleFullUpdate(data) {
        const { streams, layout } = data;
        this.updateGridLayout(layout);
        this.syncStreams(streams);
        this.updateEmptyState(streams.length === 0);
        if (data.spotlight !== undefined) {
            this.handleSpotlight({ stream_id: data.spotlight });
        }
    }

    handleMaxReconnectAttempts() {
        this.disconnectedSince = null;
        this.stopDisconnectTimer();
        this.updateConnectionStatus('disconnected');
        if (this.disconnectOverlay) {
            const messageEl = this.disconnectOverlay.querySelector('.overlay-message');
            if (messageEl) {
                messageEl.textContent = 'Conexión perdida. Recargá la página.';
            }
            const spinnerEl = this.disconnectOverlay.querySelector('.spinner');
            if (spinnerEl) {
                spinnerEl.classList.add('hidden');
            }
            const durationEl = this.disconnectOverlay.querySelector('.overlay-duration');
            if (durationEl && !durationEl.querySelector('.reload-btn')) {
                durationEl.textContent = '';
                const reloadBtn = document.createElement('button');
                reloadBtn.type = 'button';
                reloadBtn.className = 'btn btn-primary reload-btn';
                reloadBtn.textContent = 'Recargar página';
                reloadBtn.addEventListener('click', () => window.location.reload());
                durationEl.appendChild(reloadBtn);
            }
            this.disconnectOverlay.classList.remove('hidden');
        }
    }

    handleStreamAdded(data) {
        const { stream, layout } = data;
        this.updateGridLayout(layout);

        if (!this.players.has(stream.id)) {
            this.addPlayer(stream);
        }

        this.updateEmptyState(false);
    }

    handleStreamRemoved(data) {
        const { stream_id, layout } = data;

        // Exit spotlight if the removed stream was spotlighted
        if (this.spotlightStreamId === stream_id) {
            this.exitSpotlight();
        }

        this.updateGridLayout(layout);
        this.removePlayer(stream_id);

        // Check if empty
        this.updateEmptyState(this.players.size === 0);
    }

    handleMuteChange(data) {
        const { stream_id, muted } = data;
        const player = this.players.get(stream_id);
        if (player) {
            this.updatePlayerMuteState(player, muted);
            this.reloadPlayerWithMuteState(player);
        }
    }

    handleLocalMuteToggle(btn) {
        const streamId = btn.dataset.streamId;
        const player = this.players.get(streamId);
        if (!player) return;

        // Toggle local mute state
        const newMuted = !player.muted;
        this.updatePlayerMuteState(player, newMuted);

        // Reload iframe with new mute state
        this.reloadPlayerWithMuteState(player);
    }

    updateGridLayout(layout) {
        // When in spotlight mode, save the new layout but don't apply it yet
        if (this.spotlightStreamId) {
            this.savedLayout = layout;
            return;
        }
        const [rows, cols] = layout;
        this.container.style.setProperty('--rows', rows);
        this.container.style.setProperty('--cols', cols);
    }

    updateEmptyState(isEmpty) {
        this.emptyState.classList.toggle('hidden', !isEmpty);
        this.container.classList.toggle('hidden', isEmpty);
    }

    syncStreams(streams) {
        const currentIds = new Set(this.players.keys());
        const newIds = new Set(streams.map(s => s.id));

        // Remove streams that no longer exist
        for (const id of currentIds) {
            if (!newIds.has(id)) {
                this.removePlayer(id);
            }
        }

        // Add or update streams
        for (const stream of streams) {
            if (!this.players.has(stream.id)) {
                this.addPlayer(stream);
            } else {
                // Update existing player
                const player = this.players.get(stream.id);
                if (player.muted !== stream.muted) {
                    this.updatePlayerMuteState(player, stream.muted);
                }
            }
        }
    }

    addPlayer(stream) {
        const wrapper = document.createElement('div');
        wrapper.className = 'stream-wrapper';
        wrapper.dataset.streamId = stream.id;
        wrapper.dataset.platform = stream.platform;

        const iframe = document.createElement('iframe');
        iframe.src = this.buildEmbedUrl(stream);
        iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
        iframe.allowFullscreen = true;
        iframe.loading = 'lazy';
        iframe.referrerPolicy = 'strict-origin-when-cross-origin';

        const overlay = document.createElement('div');
        overlay.className = 'stream-overlay';
        overlay.innerHTML = `
            <span class="stream-title">${this.escapeHtml(stream.title)}</span>
            <button class="mute-btn ${stream.muted ? 'muted' : ''}"
                    data-stream-id="${stream.id}"
                    title="${stream.muted ? 'Unmute' : 'Mute'}">
                ${stream.muted ? '🔇' : '🔊'}
            </button>
        `;

        wrapper.appendChild(iframe);
        wrapper.appendChild(overlay);
        this.container.appendChild(wrapper);

        this.players.set(stream.id, {
            wrapper,
            iframe,
            stream,
            muted: stream.muted
        });
    }

    removePlayer(streamId) {
        const player = this.players.get(streamId);
        if (player) {
            player.wrapper.remove();
            this.players.delete(streamId);
        }
    }

    updatePlayerMuteState(player, muted) {
        player.muted = muted;
        const btn = player.wrapper.querySelector('.mute-btn');
        if (btn) {
            btn.classList.toggle('muted', muted);
            btn.textContent = muted ? '🔇' : '🔊';
            btn.title = muted ? 'Unmute' : 'Mute';
        }
    }

    reloadPlayerWithMuteState(player) {
        const stream = { ...player.stream, muted: player.muted };
        player.iframe.src = this.buildEmbedUrl(stream);
    }

    buildEmbedUrl(stream) {
        let url = stream.embed_url;
        const params = new URLSearchParams();

        switch (stream.platform) {
            case 'youtube':
                params.set('autoplay', '1');
                params.set('mute', stream.muted ? '1' : '0');
                params.set('enablejsapi', '1');
                params.set('origin', window.location.origin);
                params.set('rel', '0');
                break;

            case 'twitch':
                // Twitch params are in the URL already
                // Just update muted state
                if (url.includes('muted=')) {
                    url = url.replace(/muted=(true|false)/, `muted=${stream.muted}`);
                } else {
                    const separator = url.includes('?') ? '&' : '?';
                    url = `${url}${separator}muted=${stream.muted}`;
                }
                return url;

            case 'vimeo':
                params.set('autoplay', '1');
                params.set('muted', stream.muted ? '1' : '0');
                params.set('background', '0');
                break;
        }

        const separator = url.includes('?') ? '&' : '?';
        return `${url}${separator}${params.toString()}`;
    }

    handleSpotlight(data) {
        const streamId = data.stream_id || null;

        if (streamId) {
            // Only enter spotlight if the stream exists
            if (this.players.has(streamId)) {
                this.enterSpotlight(streamId);
            }
        } else {
            this.exitSpotlight();
        }
    }

    enterSpotlight(streamId) {
        // Save current layout before overriding
        if (!this.spotlightStreamId) {
            const rows = this.container.style.getPropertyValue('--rows');
            const cols = this.container.style.getPropertyValue('--cols');
            this.savedLayout = [parseInt(rows) || 1, parseInt(cols) || 1];
        }

        this.spotlightStreamId = streamId;

        // Set grid to 1x1
        this.container.style.setProperty('--rows', 1);
        this.container.style.setProperty('--cols', 1);

        // Add spotlight class to container
        this.container.classList.add('spotlight-mode');

        // Mark the spotlighted stream and hide others
        for (const [id, player] of this.players) {
            if (id === streamId) {
                player.wrapper.classList.add('spotlighted');
            } else {
                player.wrapper.classList.remove('spotlighted');
            }
        }
    }

    exitSpotlight() {
        if (!this.spotlightStreamId) return;

        this.spotlightStreamId = null;

        // Remove spotlight classes
        this.container.classList.remove('spotlight-mode');
        for (const [, player] of this.players) {
            player.wrapper.classList.remove('spotlighted');
        }

        // Restore saved layout
        if (this.savedLayout) {
            const [rows, cols] = this.savedLayout;
            this.container.style.setProperty('--rows', rows);
            this.container.style.setProperty('--cols', cols);
            this.savedLayout = null;
        }
    }

    toggleFullscreen(element) {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            element.requestFullscreen().catch(err => {
                console.error('Fullscreen error:', err);
            });
        }
    }

    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

// Initialize viewer when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.viewer = new StreamViewer();
});
