// CommunicationX Main JavaScript

class CommunicationX {
    constructor() {
        this.init();
        this.bindEvents();
        this.initSocket();
    }

    init() {
        // Initialize tooltips if using Bootstrap
        if (typeof bootstrap !== 'undefined') {
            var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }

        // Auto-redirect from splash screen
        if (window.location.pathname === '/' && document.querySelector('.splash-screen')) {
            setTimeout(() => {
                window.location.href = '/landing';
            }, 3000);
        }

        // Auto-focus message inputs
        const messageInput = document.querySelector('.message-input');
        if (messageInput) {
            messageInput.focus();
        }
    }

    bindEvents() {
        // Modal controls
        this.bindModalEvents();

        // Form submissions
        this.bindFormEvents();

        // Message input events
        this.bindMessageEvents();

        // Call events
        this.bindCallEvents();
    }

    bindCallEvents() {
        // Call control buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-action="start-call"]')) {
                const userId = e.target.dataset.userId;
                const callType = e.target.dataset.callType || 'audio';
                this.initiateCall(userId, callType);
            }
        });
    }

    bindModalEvents() {
        // Handle modal opening/closing
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-modal]')) {
                const modalId = e.target.dataset.modal;
                this.openModal(modalId);
            }

            if (e.target.matches('.modal-close')) {
                this.closeModal(e.target.closest('.modal'));
            }
        });
    }

    bindFormEvents() {
        // Handle form submissions with loading states
        document.addEventListener('submit', (e) => {
            const form = e.target;
            if (form.classList.contains('needs-validation')) {
                e.preventDefault();
                e.stopPropagation();

                if (form.checkValidity()) {
                    this.showLoadingState(form);
                    // Add timeout to prevent infinite loading
                    setTimeout(() => {
                        this.hideLoadingState(form);
                    }, 10000);
                    form.submit();
                }

                form.classList.add('was-validated');
            }
        });

        // Add character counters to text inputs
        document.querySelectorAll('textarea[maxlength], input[maxlength]').forEach(input => {
            this.addCharacterCounter(input);
        });
    }

    addCharacterCounter(input) {
        const maxLength = input.getAttribute('maxlength');
        if (!maxLength) return;

        const counter = document.createElement('small');
        counter.className = 'form-text text-muted character-counter';
        input.parentNode.appendChild(counter);

        const updateCounter = () => {
            const remaining = maxLength - input.value.length;
            counter.textContent = `${remaining} characters remaining`;
            counter.style.color = remaining < 50 ? '#dc3545' : '#6c757d';
        };

        input.addEventListener('input', updateCounter);
        updateCounter();
    }

    bindMessageEvents() {
        // Enter key to send message
        document.addEventListener('keydown', (e) => {
            if (e.target.classList.contains('message-input')) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    const form = e.target.closest('form');
                    if (form && e.target.value.trim()) {
                        form.submit();
                    }
                }
            }
        });

        // Auto-resize textarea
        document.addEventListener('input', (e) => {
            if (e.target.classList.contains('message-input')) {
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
            }
        });
    }

    initSocket() {
        if (typeof io !== 'undefined') {
            // Initialize Socket.IO with better connection handling
            this.socket = io({
                transports: ['websocket', 'polling'],
                upgrade: true,
                rememberUpgrade: true,
                timeout: 20000,
                forceNew: false,
                reconnection: true,
                reconnectionDelay: 1000,
                reconnectionAttempts: 5,
                maxReconnectionAttempts: 5
            });

            this.socket.on('connect', () => {
                console.log('Connected to server');
            });

            this.socket.on('disconnect', (reason) => {
                console.log('Disconnected from server:', reason);
                if (reason === 'io server disconnect') {
                    // Server disconnected, reconnect manually
                    this.socket.connect();
                }
            });

            this.socket.on('connect_error', (error) => {
                console.log('Connection error:', error);
            });

            // Call events
            this.socket.on('incoming_call', (data) => {
                this.handleIncomingCall(data);
            });

            this.socket.on('call_ended', (data) => {
                this.handleCallEnded(data);
            });
        }
    }

    showModal(modal) {
        modal.classList.add('show');
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    hideModal(modal) {
        modal.classList.remove('show');
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    initiateCall(userId, callType) {
        window.location.href = `/call/${userId}/${callType}`;
    }

    openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'block';
        }
    }

    closeModal(modal) {
        if (modal) {
            modal.style.display = 'none';
        }
    }

    handleIncomingCall(data) {
        const accept = confirm(`Incoming ${data.call_type} call from ${data.caller_name}. Accept?`);
        if (accept) {
            window.location.href = `/join_call/${data.call_id}`;
        } else {
            // Decline call
            fetch(`/decline_call/${data.call_id}`, { method: 'POST' });
        }
    }

    handleCallEnded(data) {
        this.showNotification('Call ended', 'info');
        if (window.location.pathname.includes('/call/')) {
            window.location.href = '/home';
        }
    }

    // Utility functions
    formatTime(date) {
        return new Intl.DateTimeFormat('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        }).format(new Date(date));
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    showLoadingState(form) {
        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.setAttribute('data-original-text', submitBtn.innerHTML);
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
        }
    }

    hideLoadingState(form) {
        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = false;
            const originalText = submitBtn.getAttribute('data-original-text');
            if (originalText) {
                submitBtn.innerHTML = originalText;
            }
        }
    }
}

// Message interaction functions
function toggleMessageMenu(messageId) {
    const dropdown = document.getElementById(`dropdown-${messageId}`);
    const emojiPicker = document.getElementById(`emoji-picker-${messageId}`);
    
    // Close all other dropdowns
    document.querySelectorAll('.message-dropdown').forEach(d => {
        if (d.id !== `dropdown-${messageId}`) {
            d.style.display = 'none';
        }
    });
    
    // Close emoji picker
    if (emojiPicker) emojiPicker.style.display = 'none';
    
    // Toggle current dropdown
    dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
}

function showEmojiPicker(messageId) {
    const emojiPicker = document.getElementById(`emoji-picker-${messageId}`);
    const dropdown = document.getElementById(`dropdown-${messageId}`);
    
    dropdown.style.display = 'none';
    emojiPicker.style.display = emojiPicker.style.display === 'none' ? 'block' : 'none';
}

function addReaction(messageId, emoji) {
    fetch(`/messages/${messageId}/react`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ emoji: emoji })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            location.reload(); // Refresh to show updated reactions
        }
    })
    .catch(error => console.error('Error adding reaction:', error));
    
    // Close emoji picker
    document.getElementById(`emoji-picker-${messageId}`).style.display = 'none';
}

function deleteMessage(messageId) {
    if (confirm('Are you sure you want to delete this message? This action cannot be undone.')) {
        fetch(`/messages/${messageId}/delete`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                location.reload();
            } else {
                alert('Error deleting message');
            }
        })
        .catch(error => console.error('Error deleting message:', error));
    }
}

function replyToMessage(messageId) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`).closest('.message');
    const messageContent = messageElement.querySelector('.message-content').textContent;
    const messageAuthor = messageElement.querySelector('.message-author').textContent;
    
    const messageInput = document.querySelector('.message-input');
    messageInput.value = `@${messageAuthor} `;
    messageInput.setAttribute('data-reply-to', messageId);
    messageInput.focus();
    
    // Add reply indicator
    const replyIndicator = document.createElement('div');
    replyIndicator.className = 'reply-indicator';
    replyIndicator.innerHTML = `
        <i class="fas fa-reply"></i> Replying to ${messageAuthor}: ${messageContent.substring(0, 50)}...
        <button onclick="cancelReply()" class="btn-sm btn-secondary"><i class="fas fa-times"></i></button>
    `;
    messageInput.parentNode.insertBefore(replyIndicator, messageInput);
}

function cancelReply() {
    const messageInput = document.querySelector('.message-input');
    messageInput.removeAttribute('data-reply-to');
    document.querySelector('.reply-indicator')?.remove();
}

function forwardMessage(messageId) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`).closest('.message');
    const messageContent = messageElement.querySelector('.message-content').textContent;
    
    const recipient = prompt('Enter username to forward message to:');
    if (recipient) {
        fetch(`/messages/${messageId}/forward`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ recipient: recipient })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert('Message forwarded successfully!');
            } else {
                alert('Error forwarding message: ' + data.message);
            }
        })
        .catch(error => console.error('Error forwarding message:', error));
    }
}

function copyMessageText(messageId) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`).closest('.message');
    const messageContent = messageElement.querySelector('.message-content').textContent;
    
    navigator.clipboard.writeText(messageContent).then(() => {
        showNotification('Message copied to clipboard!', 'success');
    }).catch(err => {
        console.error('Failed to copy message:', err);
    });
}

function speakMessage(messageId) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`).closest('.message');
    const messageContent = messageElement.querySelector('.message-content').textContent;
    
    if ('speechSynthesis' in window) {
        speechSynthesis.cancel(); // Stop any ongoing speech
        const utterance = new SpeechSynthesisUtterance(messageContent);
        utterance.rate = 0.8;
        utterance.pitch = 1;
        speechSynthesis.speak(utterance);
    } else {
        alert('Speech synthesis not supported in this browser');
    }
}

function togglePinMessage(messageId) {
    fetch(`/messages/${messageId}/pin`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            location.reload();
        } else {
            alert('Error pinning/unpinning message');
        }
    })
    .catch(error => console.error('Error pinning message:', error));
}

function reportMessage(messageId) {
    const reason = prompt('Please specify the reason for reporting this message:');
    if (reason) {
        fetch(`/messages/${messageId}/report`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ reason: reason })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert('Message reported successfully');
            } else {
                alert('Error reporting message');
            }
        })
        .catch(error => console.error('Error reporting message:', error));
    }
}

function sendAudioMessage() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert('Audio recording not supported in this browser');
        return;
    }

    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            const mediaRecorder = new MediaRecorder(stream);
            const audioChunks = [];

            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                const formData = new FormData();
                formData.append('audio', audioBlob, 'voice_message.wav');

                fetch('/send_audio_message', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        location.reload();
                    } else {
                        alert('Error sending audio message');
                    }
                })
                .catch(error => console.error('Error sending audio:', error));

                stream.getTracks().forEach(track => track.stop());
            };

            // Start recording
            mediaRecorder.start();
            
            // Stop recording after 30 seconds or when user clicks stop
            const stopButton = document.createElement('button');
            stopButton.textContent = 'Stop Recording';
            stopButton.className = 'btn btn-danger';
            stopButton.onclick = () => {
                mediaRecorder.stop();
                stopButton.remove();
            };
            
            document.body.appendChild(stopButton);
            
            setTimeout(() => {
                if (mediaRecorder.state === 'recording') {
                    mediaRecorder.stop();
                    stopButton.remove();
                }
            }, 30000);
        })
        .catch(error => {
            console.error('Error accessing microphone:', error);
            alert('Error accessing microphone');
        });
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 24px;
        border-radius: 4px;
        color: white;
        font-weight: 500;
        z-index: 9999;
        max-width: 300px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        background-color: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#17a2b8'};
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Close dropdowns when clicking outside
document.addEventListener('click', function(event) {
    if (!event.target.closest('.message-actions')) {
        document.querySelectorAll('.message-dropdown, .emoji-picker').forEach(d => {
            d.style.display = 'none';
        });
    }
});

// Initialize the application
window.addEventListener('DOMContentLoaded', () => {
    window.communicationX = new CommunicationX();
});

// Service Worker registration for PWA capabilities
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
            .then((registration) => {
                console.log('SW registered: ', registration);
            })
            .catch((registrationError) => {
                console.log('SW registration failed: ', registrationError);
            });
    });
}

// Handle online/offline status
window.addEventListener('online', () => {
    document.body.classList.remove('offline');
    window.communicationX?.showNotification('Connection restored', 'success');
});

window.addEventListener('offline', () => {
    document.body.classList.add('offline');
    window.communicationX?.showNotification('Connection lost', 'warning');
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K for quick search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.querySelector('#quick-search');
        if (searchInput) {
            searchInput.focus();
        }
    }

    // Ctrl/Cmd + Enter to send message
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        const messageInput = document.querySelector('.message-input:focus');
        if (messageInput) {
            const form = messageInput.closest('form');
            if (form && messageInput.value.trim()) {
                form.submit();
            }
        }
    }
});

// Modal functionality
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'flex';
        modal.style.justifyContent = 'center';
        modal.style.alignItems = 'center';
        modal.style.position = 'fixed';
        modal.style.top = '0';
        modal.style.left = '0';
        modal.style.width = '100%';
        modal.style.height = '100%';
        modal.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
        modal.style.zIndex = '1000';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
    }
}

// Enhanced modal handling
document.addEventListener('DOMContentLoaded', function() {
    // Handle modal triggers
    document.querySelectorAll('[data-modal-target]').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const modalId = this.getAttribute('data-modal-target');
            openModal(modalId);
        });
    });

    // Handle modal close buttons
    document.querySelectorAll('.modal-close').forEach(button => {
        button.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) {
                modal.style.display = 'none';
            }
        });
    });

    // Close modal when clicking outside
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                this.style.display = 'none';
            }
        });
    });

    // Form validation for server creation
    const createServerForm = document.querySelector('#createServerModal form');
    if (createServerForm) {
        createServerForm.addEventListener('submit', function(e) {
            const serverName = this.querySelector('input[name="server_name"]').value.trim();
            if (serverName.length < 3) {
                e.preventDefault();
                alert('Server name must be at least 3 characters long.');
                return false;
            }
            if (serverName.length > 100) {
                e.preventDefault();
                alert('Server name is too long. Maximum 100 characters allowed.');
                return false;
            }
        });
    }
});

// Close modal when clicking outside
window.onclick = function(event) {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    });
}

// Invitation functionality
async function createInvitation(event) {
    event.preventDefault();

    const formData = new FormData(event.target);

    try {
        const response = await fetch('/create_invitation', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            document.getElementById('invitationUrl').textContent = data.invite_url;
            document.getElementById('invitationResult').style.display = 'block';
        } else {
            alert('Error creating invitation: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        alert('Error creating invitation: ' + error.message);
    }
}

function copyInvitationUrl() {
    const urlElement = document.getElementById('invitationUrl');
    const url = urlElement.textContent;

    navigator.clipboard.writeText(url).then(function() {
        // Change button text temporarily
        const button = event.target;
        const originalText = button.textContent;
        button.textContent = 'Copied!';
        button.style.backgroundColor = '#28a745';

        setTimeout(() => {
            button.textContent = originalText;
            button.style.backgroundColor = '';
        }, 2000);
    }).catch(function(err) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = url;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);

        alert('Invitation URL copied to clipboard!');
    });
}

// Message Management Functions
function deleteMessage(messageId) {
    if (confirm('Are you sure you want to delete this message?')) {
        fetch(`/message/${messageId}/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        }).then(response => {
            if (response.ok) {
                document.querySelector(`[data-message-id="${messageId}"]`).remove();
                showNotification('Message deleted', 'success');
            }
        });
    }
}

function toggleReaction(messageId, emoji) {
    fetch(`/message/${messageId}/react`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ emoji })
    }).then(response => response.json())
    .then(data => {
        updateReactionDisplay(messageId, emoji, data.action);
    });
}

function updateReactionDisplay(messageId, emoji, action) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    let reactionsContainer = messageElement.querySelector('.message-reactions');
    
    if (!reactionsContainer) {
        reactionsContainer = document.createElement('div');
        reactionsContainer.className = 'message-reactions';
        messageElement.querySelector('.message-content').appendChild(reactionsContainer);
    }

    let reactionElement = reactionsContainer.querySelector(`[data-emoji="${emoji}"]`);
    
    if (action === 'added') {
        if (!reactionElement) {
            reactionElement = document.createElement('span');
            reactionElement.className = 'reaction';
            reactionElement.dataset.emoji = emoji;
            reactionElement.dataset.messageId = messageId;
            reactionElement.innerHTML = `${emoji} <span class="reaction-count">1</span>`;
            reactionsContainer.appendChild(reactionElement);
        } else {
            const countElement = reactionElement.querySelector('.reaction-count');
            const currentCount = parseInt(countElement.textContent);
            countElement.textContent = currentCount + 1;
        }
    } else if (action === 'removed' && reactionElement) {
        const countElement = reactionElement.querySelector('.reaction-count');
        const currentCount = parseInt(countElement.textContent);
        if (currentCount <= 1) {
            reactionElement.remove();
        } else {
            countElement.textContent = currentCount - 1;
        }
    }
}

function togglePin(messageId) {
    fetch(`/message/${messageId}/pin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    }).then(response => response.json())
    .then(data => {
        const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
        const pinIndicator = messageElement.querySelector('.pinned-indicator');
        
        if (data.pinned && !pinIndicator) {
            const indicator = document.createElement('span');
            indicator.className = 'pinned-indicator';
            indicator.innerHTML = '<i class="fas fa-thumbtack"></i>';
            messageElement.querySelector('.message-header').appendChild(indicator);
        } else if (!data.pinned && pinIndicator) {
            pinIndicator.remove();
        }
        showNotification(data.pinned ? 'Message pinned' : 'Message unpinned', 'success');
    });
}

function reportMessage(messageId) {
    const reason = prompt('Report reason:\n1. Spam\n2. Harassment\n3. Inappropriate Content\n4. Violence\n5. Other');
    const reasons = ['Spam', 'Harassment', 'Inappropriate Content', 'Violence', 'Other'];
    
    if (reason && reason >= 1 && reason <= 5) {
        const description = prompt('Additional details (optional):') || '';
        fetch(`/message/${messageId}/report`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: reasons[reason - 1], description })
        }).then(response => {
            if (response.ok) {
                showNotification('Message reported', 'success');
            }
        });
    }
}

function replyToMessage(messageId) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    const authorName = messageElement.querySelector('.message-author').textContent;
    
    const messageInput = document.querySelector('textarea[name="message"]');
    if (messageInput) {
        messageInput.focus();
        messageInput.dataset.replyTo = messageId;
        
        let replyIndicator = document.querySelector('.reply-indicator-input');
        if (!replyIndicator) {
            replyIndicator = document.createElement('div');
            replyIndicator.className = 'reply-indicator-input';
            replyIndicator.style.cssText = 'background: #e3f2fd; padding: 8px; border-left: 3px solid #2196f3; margin-bottom: 8px; border-radius: 4px; display: flex; justify-content: space-between; align-items: center;';
            messageInput.parentNode.insertBefore(replyIndicator, messageInput);
        }
        
        replyIndicator.innerHTML = `
            <span><i class="fas fa-reply"></i> Replying to ${authorName}</span>
            <button type="button" class="cancel-reply" style="background: none; border: none; font-size: 16px; cursor: pointer;">×</button>
        `;

        replyIndicator.querySelector('.cancel-reply').addEventListener('click', () => {
            replyIndicator.remove();
            messageInput.removeAttribute('data-reply-to');
        });
    }
}

function forwardMessage(messageId) {
    const recipientId = prompt('Enter recipient user ID for forwarding to DM:');
    if (recipientId) {
        fetch(`/message/${messageId}/forward`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ recipient_id: recipientId })
        }).then(response => {
            if (response.ok) {
                showNotification('Message forwarded', 'success');
            }
        });
    }
}

function copyMessageText(messageId) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    const messageText = messageElement.querySelector('.message-text').textContent;
    
    navigator.clipboard.writeText(messageText).then(() => {
        showNotification('Text copied to clipboard', 'success');
    });
}

function speakMessage(messageId) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    const messageText = messageElement.querySelector('.message-text').textContent;
    
    if ('speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(messageText);
        speechSynthesis.speak(utterance);
        showNotification('Speaking message', 'info');
    } else {
        showNotification('Speech synthesis not supported', 'error');
    }
}

function showEmojiPicker(messageId) {
    const emojis = ['👍', '👎', '❤️', '😂', '😮', '😢', '😡', '🎉', '👏', '🔥'];
    const emojiPicker = document.createElement('div');
    emojiPicker.className = 'emoji-picker';
    emojiPicker.style.cssText = 'position: absolute; background: white; border: 1px solid #ccc; border-radius: 8px; padding: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); z-index: 1000; display: flex; gap: 4px;';
    emojiPicker.innerHTML = emojis.map(emoji => 
        `<button class="emoji-btn" data-emoji="${emoji}" style="background: none; border: none; font-size: 20px; padding: 4px; cursor: pointer; border-radius: 4px;" onmouseover="this.style.background='#f0f0f0'" onmouseout="this.style.background='none'">${emoji}</button>`
    ).join('');

    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    messageElement.style.position = 'relative';
    messageElement.appendChild(emojiPicker);

    emojiPicker.addEventListener('click', (e) => {
        if (e.target.classList.contains('emoji-btn')) {
            const emoji = e.target.dataset.emoji;
            toggleReaction(messageId, emoji);
            emojiPicker.remove();
        }
    });

    setTimeout(() => {
        document.addEventListener('click', function removeEmojiPicker(e) {
            if (!emojiPicker.contains(e.target)) {
                emojiPicker.remove();
                document.removeEventListener('click', removeEmojiPicker);
            }
        });
    }, 100);
}

function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.style.cssText = 'position: fixed; top: 20px; right: 20px; padding: 12px 20px; border-radius: 4px; color: white; z-index: 10000; opacity: 0; transition: opacity 0.3s;';
    
    if (type === 'success') notification.style.background = '#4caf50';
    else if (type === 'error') notification.style.background = '#f44336';
    else notification.style.background = '#2196f3';
    
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => notification.style.opacity = '1', 10);
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Message dropdown functionality
document.addEventListener('click', (e) => {
    if (e.target.closest('.message-menu-btn')) {
        const btn = e.target.closest('.message-menu-btn');
        const messageId = btn.dataset.messageId;
        const dropdown = document.getElementById(`dropdown-${messageId}`);
        
        // Hide all other dropdowns
        document.querySelectorAll('.message-dropdown').forEach(d => {
            if (d.id !== `dropdown-${messageId}`) {
                d.style.display = 'none';
            }
        });
        
        // Toggle current dropdown
        dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
    }
    
    // Close dropdowns when clicking outside
    if (!e.target.closest('.message-actions')) {
        document.querySelectorAll('.message-dropdown').forEach(d => {
            d.style.display = 'none';
        });
    }
});

// Delegate click events for message actions
document.addEventListener('click', (e) => {
    const messageId = e.target.dataset.messageId;
    
    if (e.target.closest('.delete-btn')) {
        deleteMessage(messageId);
    } else if (e.target.closest('.react-btn')) {
        showEmojiPicker(messageId);
    } else if (e.target.closest('.pin-btn')) {
        togglePin(messageId);
    } else if (e.target.closest('.report-btn')) {
        reportMessage(messageId);
    } else if (e.target.closest('.reply-btn')) {
        replyToMessage(messageId);
    } else if (e.target.closest('.forward-btn')) {
        forwardMessage(messageId);
    } else if (e.target.closest('.copy-btn')) {
        copyMessageText(messageId);
    } else if (e.target.closest('.speak-btn')) {
        speakMessage(messageId);
    } else if (e.target.closest('.reaction')) {
        const emoji = e.target.closest('.reaction').dataset.emoji;
        toggleReaction(messageId, emoji);
    }
});