/**
 * Animated Message Status Indicators
 * Handles real-time message status updates with smooth animations
 */

class MessageStatusManager {
    constructor() {
        this.statusTransitions = {
            'sending': ['sent', 'failed'],
            'sent': ['delivered', 'failed'],
            'delivered': ['read'],
            'read': [],
            'failed': ['sending'] // Allow retry
        };
        
        this.statusLabels = {
            'sending': 'Sending...',
            'sent': 'Sent',
            'delivered': 'Delivered',
            'read': 'Read',
            'failed': 'Failed to send'
        };
        
        this.init();
    }
    
    init() {
        this.setupSocketListeners();
        this.setupRetryHandlers();
        this.updateExistingMessages();
    }
    
    /**
     * Create status indicator HTML
     */
    createStatusIndicator(status, messageId, timestamp = null) {
        const tooltipText = this.getStatusTooltip(status, timestamp);
        
        return `
            <div class="message-status ${status}" data-message-id="${messageId}">
                <div class="status-icon"></div>
                <div class="status-tooltip">${tooltipText}</div>
            </div>
        `;
    }
    
    /**
     * Update message status with animation
     */
    updateMessageStatus(messageId, newStatus, timestamp = null, readBy = null) {
        const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!messageElement) return;
        
        const statusElement = messageElement.querySelector('.message-status');
        if (!statusElement) {
            // Create status indicator if it doesn't exist
            const statusHtml = this.createStatusIndicator(newStatus, messageId, timestamp);
            messageElement.insertAdjacentHTML('beforeend', statusHtml);
            return;
        }
        
        const currentStatus = this.getCurrentStatus(statusElement);
        
        // Check if transition is valid
        if (!this.isValidTransition(currentStatus, newStatus)) {
            console.warn(`Invalid status transition: ${currentStatus} -> ${newStatus}`);
            return;
        }
        
        // Animate status change
        this.animateStatusChange(statusElement, currentStatus, newStatus, timestamp, readBy);
    }
    
    /**
     * Animate status change with smooth transition
     */
    animateStatusChange(statusElement, oldStatus, newStatus, timestamp, readBy) {
        // Remove old status class
        statusElement.classList.remove(oldStatus);
        
        // Add transition class for smooth animation
        statusElement.classList.add('transitioning');
        
        // Small delay for transition effect
        setTimeout(() => {
            statusElement.classList.remove('transitioning');
            statusElement.classList.add(newStatus);
            
            // Update tooltip
            const tooltip = statusElement.querySelector('.status-tooltip');
            if (tooltip) {
                tooltip.textContent = this.getStatusTooltip(newStatus, timestamp);
            }
            
            // Add read receipts for group messages
            if (newStatus === 'read' && readBy && readBy.length > 0) {
                this.addReadReceipts(statusElement.parentElement, readBy);
            }
            
            // Trigger custom event
            this.triggerStatusChangeEvent(statusElement, oldStatus, newStatus);
        }, 150);
    }
    
    /**
     * Add read receipt avatars
     */
    addReadReceipts(messageElement, readBy) {
        // Remove existing read receipts
        const existingReceipts = messageElement.querySelector('.read-receipts');
        if (existingReceipts) {
            existingReceipts.remove();
        }
        
        if (readBy.length === 0) return;
        
        const receiptsHtml = `
            <div class="read-receipts">
                ${readBy.map(user => `
                    <img src="${user.avatar || '/static/assets/default-avatar.png'}" 
                         alt="${user.username}" 
                         title="Read by ${user.username}"
                         class="read-receipt-avatar">
                `).join('')}
                ${readBy.length > 3 ? `<span class="read-count">+${readBy.length - 3}</span>` : ''}
            </div>
        `;
        
        messageElement.insertAdjacentHTML('beforeend', receiptsHtml);
    }
    
    /**
     * Setup socket listeners for real-time status updates
     */
    setupSocketListeners() {
        if (typeof socket === 'undefined') return;
        
        // Message status updates
        socket.on('message_status_update', (data) => {
            this.updateMessageStatus(
                data.message_id, 
                data.status, 
                data.timestamp,
                data.read_by
            );
        });
        
        // Typing indicators
        socket.on('user_typing', (data) => {
            this.showTypingIndicator(data.user_id, data.username, data.channel_id);
        });
        
        socket.on('user_stopped_typing', (data) => {
            this.hideTypingIndicator(data.user_id, data.channel_id);
        });
        
        // Message delivery confirmations
        socket.on('message_delivered', (data) => {
            this.updateMessageStatus(data.message_id, 'delivered', data.timestamp);
        });
        
        // Read receipts
        socket.on('message_read', (data) => {
            this.updateMessageStatus(data.message_id, 'read', data.timestamp, data.read_by);
        });
    }
    
    /**
     * Show typing indicator
     */
    showTypingIndicator(userId, username, channelId) {
        const chatContainer = document.querySelector(`[data-channel-id="${channelId}"] .messages-container`);
        if (!chatContainer) return;
        
        // Remove existing typing indicator for this user
        this.hideTypingIndicator(userId, channelId);
        
        const typingHtml = `
            <div class="typing-indicator" data-user-id="${userId}" data-channel-id="${channelId}">
                <span class="typing-text">${username} is typing</span>
                <div class="typing-dots">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;
        
        chatContainer.insertAdjacentHTML('beforeend', typingHtml);
        this.scrollToBottom(chatContainer);
    }
    
    /**
     * Hide typing indicator
     */
    hideTypingIndicator(userId, channelId) {
        const indicator = document.querySelector(
            `.typing-indicator[data-user-id="${userId}"][data-channel-id="${channelId}"]`
        );
        
        if (indicator) {
            indicator.style.animation = 'typing-fade-out 0.3s ease forwards';
            setTimeout(() => indicator.remove(), 300);
        }
    }
    
    /**
     * Setup retry handlers for failed messages
     */
    setupRetryHandlers() {
        document.addEventListener('click', (e) => {
            if (e.target.closest('.message-status.failed')) {
                const messageElement = e.target.closest('[data-message-id]');
                if (messageElement) {
                    this.retryMessage(messageElement.dataset.messageId);
                }
            }
        });
    }
    
    /**
     * Retry failed message
     */
    retryMessage(messageId) {
        const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!messageElement) return;
        
        // Update status to sending
        this.updateMessageStatus(messageId, 'sending');
        
        // Get message content and resend
        const messageContent = messageElement.querySelector('.message-content');
        if (messageContent && typeof sendMessage === 'function') {
            sendMessage(messageContent.textContent, messageId);
        }
    }
    
    /**
     * Get current status from element
     */
    getCurrentStatus(statusElement) {
        for (const status of Object.keys(this.statusLabels)) {
            if (statusElement.classList.contains(status)) {
                return status;
            }
        }
        return 'sending';
    }
    
    /**
     * Check if status transition is valid
     */
    isValidTransition(currentStatus, newStatus) {
        if (currentStatus === newStatus) return false;
        return this.statusTransitions[currentStatus]?.includes(newStatus) || false;
    }
    
    /**
     * Get tooltip text for status
     */
    getStatusTooltip(status, timestamp) {
        const label = this.statusLabels[status];
        if (timestamp) {
            const time = new Date(timestamp).toLocaleTimeString();
            return `${label} at ${time}`;
        }
        return label;
    }
    
    /**
     * Trigger custom status change event
     */
    triggerStatusChangeEvent(element, oldStatus, newStatus) {
        const event = new CustomEvent('messageStatusChanged', {
            detail: {
                messageId: element.dataset.messageId,
                oldStatus,
                newStatus,
                element
            }
        });
        document.dispatchEvent(event);
    }
    
    /**
     * Update existing messages with status indicators
     */
    updateExistingMessages() {
        const messages = document.querySelectorAll('[data-message-id]');
        messages.forEach(message => {
            if (!message.querySelector('.message-status')) {
                const messageId = message.dataset.messageId;
                const status = message.dataset.status || 'sent';
                const statusHtml = this.createStatusIndicator(status, messageId);
                message.insertAdjacentHTML('beforeend', statusHtml);
            }
        });
    }
    
    /**
     * Mark message as sent
     */
    markAsSent(messageId, timestamp = null) {
        this.updateMessageStatus(messageId, 'sent', timestamp || new Date().toISOString());
    }
    
    /**
     * Mark message as delivered
     */
    markAsDelivered(messageId, timestamp = null) {
        this.updateMessageStatus(messageId, 'delivered', timestamp || new Date().toISOString());
    }
    
    /**
     * Mark message as read
     */
    markAsRead(messageId, readBy = null, timestamp = null) {
        this.updateMessageStatus(messageId, 'read', timestamp || new Date().toISOString(), readBy);
    }
    
    /**
     * Mark message as failed
     */
    markAsFailed(messageId, error = null) {
        this.updateMessageStatus(messageId, 'failed');
        
        if (error) {
            console.error(`Message ${messageId} failed:`, error);
        }
    }
    
    /**
     * Scroll to bottom of chat container
     */
    scrollToBottom(container) {
        container.scrollTop = container.scrollHeight;
    }
    
    /**
     * Send typing notification
     */
    sendTypingNotification(channelId) {
        if (typeof socket !== 'undefined') {
            socket.emit('typing', { channel_id: channelId });
        }
    }
    
    /**
     * Stop typing notification
     */
    stopTypingNotification(channelId) {
        if (typeof socket !== 'undefined') {
            socket.emit('stop_typing', { channel_id: channelId });
        }
    }
}

// Initialize message status manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.messageStatusManager = new MessageStatusManager();
});

// Add CSS for fade out animation
const additionalCSS = `
@keyframes typing-fade-out {
    from {
        opacity: 1;
        transform: translateY(0);
    }
    to {
        opacity: 0;
        transform: translateY(-10px);
    }
}

.message-status.transitioning {
    opacity: 0.5;
    transform: scale(0.95);
    transition: all 0.15s ease;
}
`;

// Inject additional CSS
const style = document.createElement('style');
style.textContent = additionalCSS;
document.head.appendChild(style);

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MessageStatusManager;
}