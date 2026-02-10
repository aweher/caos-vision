/**
 * Admin panel - stream management with real-time updates.
 */
class AdminPanel {
    constructor() {
        this.form = document.getElementById('add-stream-form');
        this.urlInput = document.getElementById('stream-url');
        this.messageEl = document.getElementById('form-message');
        this.streamsContainer = document.getElementById('streams-container');
        this.streamCountEl = document.getElementById('stream-count');
        this.layoutInfoEl = document.getElementById('layout-info');
        this.statusEl = document.getElementById('connection-status');

        this.spotlightStreamId = null;

        this.ws = new WebSocketClient('/ws/admin');
        this.setupEventHandlers();
        this.setupUI();
    }

    setupEventHandlers() {
        // Connection status
        this.ws.on('connect', () => this.updateConnectionStatus('connected'));
        this.ws.on('disconnect', () => this.updateConnectionStatus('disconnected'));

        // Stream events
        this.ws.on('stream_update', (data) => this.handleFullUpdate(data));
        this.ws.on('stream_added', (data) => this.handleStreamAdded(data));
        this.ws.on('stream_removed', (data) => this.handleStreamRemoved(data));
        this.ws.on('stream_muted', (data) => this.handleMuteChange(data));
        this.ws.on('stream_spotlight', (data) => this.handleSpotlightChange(data));
    }

    setupUI() {
        // Form submission
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.addStream();
        });

        // Refresh viewers button
        const refreshBtn = document.getElementById('refresh-viewers-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.forceRefreshViewers());
        }

        // Delegate button clicks
        this.streamsContainer.addEventListener('click', (e) => {
            const spotlightBtn = e.target.closest('.btn-spotlight');
            const muteBtn = e.target.closest('.btn-mute');
            const deleteBtn = e.target.closest('.btn-delete');

            if (spotlightBtn) {
                this.toggleSpotlight(spotlightBtn.dataset.streamId);
            } else if (muteBtn) {
                this.toggleMute(muteBtn.dataset.streamId);
            } else if (deleteBtn) {
                this.deleteStream(deleteBtn.dataset.streamId);
            }
        });
    }

    forceRefreshViewers() {
        this.ws.send({ type: 'force_viewer_refresh' });
        this.showMessage('Refresh command sent to all viewers', 'success');
    }

    updateConnectionStatus(status) {
        this.statusEl.className = `connection-status ${status}`;
        const textEl = this.statusEl.querySelector('.status-text');
        textEl.textContent = status === 'connected' ? 'Connected' : 'Reconnecting...';
    }

    handleFullUpdate(data) {
        this.renderStreamList(data.streams);
        this.updateLayoutInfo(data.layout);
    }

    handleStreamAdded(data) {
        // Request full refresh to get proper order
        this.ws.send({ type: 'request_refresh' });
        this.showMessage('Stream added successfully', 'success');
    }

    handleStreamRemoved(data) {
        const item = this.streamsContainer.querySelector(`[data-id="${data.stream_id}"]`);
        if (item) {
            item.remove();
        }
        // Clear spotlight if the removed stream was spotlighted
        if (this.spotlightStreamId === data.stream_id) {
            this.spotlightStreamId = null;
        }
        this.updateStreamCount();
        this.updateLayoutInfo(data.layout);
    }

    handleMuteChange(data) {
        const item = this.streamsContainer.querySelector(`[data-id="${data.stream_id}"]`);
        if (item) {
            const btn = item.querySelector('.btn-mute');
            btn.classList.toggle('muted', data.muted);
            btn.textContent = data.muted ? '🔇' : '🔊';
            btn.title = data.muted ? 'Unmute' : 'Mute';
        }
    }

    handleSpotlightChange(data) {
        this.spotlightStreamId = data.stream_id || null;
        this.updateSpotlightUI();
    }

    toggleSpotlight(streamId) {
        // Toggle: if same stream is already spotlighted, clear it
        const newId = this.spotlightStreamId === streamId ? null : streamId;
        this.ws.send({ type: 'spotlight_stream', stream_id: newId });
    }

    updateSpotlightUI() {
        // Remove active class from all spotlight buttons
        this.streamsContainer.querySelectorAll('.btn-spotlight').forEach(btn => {
            const isActive = btn.dataset.streamId === this.spotlightStreamId;
            btn.classList.toggle('active', isActive);
            btn.title = isActive ? 'Remove spotlight' : 'Spotlight this stream';
        });
    }

    async addStream() {
        const url = this.urlInput.value.trim();

        if (!url) {
            this.showMessage('Please enter a URL', 'error');
            return;
        }

        const submitBtn = this.form.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Adding...';
        this.hideMessage();

        try {
            const response = await fetch('/api/v1/streams', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ url })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to add stream');
            }

            this.urlInput.value = '';
            // Success message will come from WebSocket event
        } catch (error) {
            this.showMessage(error.message, 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Add Stream';
        }
    }

    async toggleMute(streamId) {
        try {
            const response = await fetch(`/api/v1/streams/${streamId}/mute`, {
                method: 'POST',
                credentials: 'include'
            });

            if (!response.ok) {
                throw new Error('Failed to toggle mute');
            }
            // UI update will come from WebSocket event
        } catch (error) {
            this.showMessage(error.message, 'error');
        }
    }

    async deleteStream(streamId) {
        if (!confirm('Are you sure you want to remove this stream?')) {
            return;
        }

        try {
            const response = await fetch(`/api/v1/streams/${streamId}`, {
                method: 'DELETE',
                credentials: 'include'
            });

            if (!response.ok) {
                throw new Error('Failed to delete stream');
            }

            this.showMessage('Stream removed', 'success');
            // UI update will come from WebSocket event
        } catch (error) {
            this.showMessage(error.message, 'error');
        }
    }

    renderStreamList(streams) {
        if (streams.length === 0) {
            this.streamsContainer.innerHTML = `
                <div class="empty-streams">
                    <p>No streams added yet. Add your first stream above.</p>
                </div>
            `;
        } else {
            this.streamsContainer.innerHTML = streams.map(stream => this.renderStreamItem(stream)).join('');
        }
        this.updateStreamCount();
    }

    renderStreamItem(stream) {
        const thumbnail = stream.thumbnail
            ? `<img class="stream-thumbnail" src="${this.escapeHtml(stream.thumbnail)}" alt="" loading="lazy">`
            : `<div class="stream-thumbnail placeholder"></div>`;

        const isSpotlighted = this.spotlightStreamId === stream.id;

        return `
            <div class="stream-item" data-id="${stream.id}">
                <div class="stream-info">
                    ${thumbnail}
                    <div class="stream-details">
                        <span class="stream-title">${this.escapeHtml(stream.title)}</span>
                        <span class="stream-platform badge badge-${stream.platform}">${stream.platform}</span>
                    </div>
                </div>
                <div class="stream-actions">
                    <button class="btn btn-icon btn-spotlight ${isSpotlighted ? 'active' : ''}"
                            data-stream-id="${stream.id}"
                            title="${isSpotlighted ? 'Remove spotlight' : 'Spotlight this stream'}">
                        🔍
                    </button>
                    <button class="btn btn-icon btn-mute ${stream.muted ? 'muted' : ''}"
                            data-stream-id="${stream.id}"
                            title="${stream.muted ? 'Unmute' : 'Mute'}">
                        ${stream.muted ? '🔇' : '🔊'}
                    </button>
                    <button class="btn btn-icon btn-delete"
                            data-stream-id="${stream.id}"
                            title="Delete stream">
                        🗑️
                    </button>
                </div>
            </div>
        `;
    }

    updateStreamCount() {
        const count = this.streamsContainer.querySelectorAll('.stream-item').length;
        this.streamCountEl.textContent = count;
    }

    updateLayoutInfo(layout) {
        this.layoutInfoEl.textContent = `${layout[0]}×${layout[1]}`;
    }

    showMessage(text, type) {
        this.messageEl.textContent = text;
        this.messageEl.className = `form-message ${type}`;
        this.messageEl.classList.remove('hidden');

        // Auto-hide after 5 seconds
        setTimeout(() => this.hideMessage(), 5000);
    }

    hideMessage() {
        this.messageEl.classList.add('hidden');
    }

    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

// Initialize admin panel when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.admin = new AdminPanel();
});
