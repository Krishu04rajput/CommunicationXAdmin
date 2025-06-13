// WebRTC Implementation for CommunicationX

class WebRTCCall {
    constructor(callId, isInitiator = false) {
        this.callId = callId;
        this.isInitiator = isInitiator;
        this.localStream = null;
        this.remoteStream = null;
        this.peerConnection = null;
        this.socket = io();
        this.isMuted = false;
        this.isCameraOff = false;
        
        this.init();
    }

    async init() {
        try {
            // Initialize peer connection
            this.setupPeerConnection();
            
            // Get user media
            await this.getUserMedia();
            
            // Setup socket events
            this.setupSocketEvents();
            
            // Join call room
            this.socket.emit('join_call', { call_id: this.callId });
            
            // If initiator, create offer
            if (this.isInitiator) {
                await this.createOffer();
            }
            
            this.setupUI();
            
        } catch (error) {
            console.error('Error initializing call:', error);
            this.handleError('Failed to initialize call. Please check your camera and microphone permissions.');
        }
    }

    setupPeerConnection() {
        const configuration = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' }
            ]
        };

        this.peerConnection = new RTCPeerConnection(configuration);

        // Handle remote stream
        this.peerConnection.ontrack = (event) => {
            console.log('Received remote stream');
            this.remoteStream = event.streams[0];
            const remoteVideo = document.getElementById('remoteVideo');
            if (remoteVideo) {
                remoteVideo.srcObject = this.remoteStream;
            }
        };

        // Handle ICE candidates
        this.peerConnection.onicecandidate = (event) => {
            if (event.candidate) {
                this.socket.emit('ice_candidate', {
                    call_id: this.callId,
                    candidate: event.candidate
                });
            }
        };

        // Handle connection state changes
        this.peerConnection.onconnectionstatechange = () => {
            console.log('Connection state:', this.peerConnection.connectionState);
            if (this.peerConnection.connectionState === 'failed') {
                this.handleError('Connection failed. Please try again.');
            }
        };
    }

    async getUserMedia() {
        try {
            const constraints = {
                video: true,
                audio: true
            };

            this.localStream = await navigator.mediaDevices.getUserMedia(constraints);
            
            // Display local video
            const localVideo = document.getElementById('localVideo');
            if (localVideo) {
                localVideo.srcObject = this.localStream;
            }

            // Add tracks to peer connection
            this.localStream.getTracks().forEach(track => {
                this.peerConnection.addTrack(track, this.localStream);
            });

        } catch (error) {
            console.error('Error accessing media devices:', error);
            throw new Error('Could not access camera and microphone');
        }
    }

    setupSocketEvents() {
        this.socket.on('user_joined', (data) => {
            console.log('User joined call:', data);
        });

        this.socket.on('user_left', (data) => {
            console.log('User left call:', data);
            this.endCall();
        });

        this.socket.on('offer', async (data) => {
            console.log('Received offer');
            await this.handleOffer(data.offer);
        });

        this.socket.on('answer', async (data) => {
            console.log('Received answer');
            await this.handleAnswer(data.answer);
        });

        this.socket.on('ice_candidate', async (data) => {
            console.log('Received ICE candidate');
            await this.handleIceCandidate(data.candidate);
        });
    }

    async createOffer() {
        try {
            const offer = await this.peerConnection.createOffer();
            await this.peerConnection.setLocalDescription(offer);
            
            this.socket.emit('offer', {
                call_id: this.callId,
                offer: offer
            });
        } catch (error) {
            console.error('Error creating offer:', error);
        }
    }

    async handleOffer(offer) {
        try {
            await this.peerConnection.setRemoteDescription(new RTCSessionDescription(offer));
            
            const answer = await this.peerConnection.createAnswer();
            await this.peerConnection.setLocalDescription(answer);
            
            this.socket.emit('answer', {
                call_id: this.callId,
                answer: answer
            });
        } catch (error) {
            console.error('Error handling offer:', error);
        }
    }

    async handleAnswer(answer) {
        try {
            await this.peerConnection.setRemoteDescription(new RTCSessionDescription(answer));
        } catch (error) {
            console.error('Error handling answer:', error);
        }
    }

    async handleIceCandidate(candidate) {
        try {
            await this.peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
        } catch (error) {
            console.error('Error handling ICE candidate:', error);
        }
    }

    setupUI() {
        // Mute button
        const muteBtn = document.getElementById('muteBtn');
        if (muteBtn) {
            muteBtn.addEventListener('click', () => this.toggleMute());
        }

        // Camera button
        const cameraBtn = document.getElementById('cameraBtn');
        if (cameraBtn) {
            cameraBtn.addEventListener('click', () => this.toggleCamera());
        }

        // End call button
        const endCallBtn = document.getElementById('endCallBtn');
        if (endCallBtn) {
            endCallBtn.addEventListener('click', () => this.endCall());
        }

        // Handle window close/refresh
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });
    }

    toggleMute() {
        if (this.localStream) {
            const audioTracks = this.localStream.getAudioTracks();
            audioTracks.forEach(track => {
                track.enabled = !track.enabled;
            });
            
            this.isMuted = !this.isMuted;
            const muteBtn = document.getElementById('muteBtn');
            if (muteBtn) {
                muteBtn.classList.toggle('active', this.isMuted);
                muteBtn.innerHTML = this.isMuted ? 
                    '<i class="fas fa-microphone-slash"></i>' : 
                    '<i class="fas fa-microphone"></i>';
            }
        }
    }

    toggleCamera() {
        if (this.localStream) {
            const videoTracks = this.localStream.getVideoTracks();
            videoTracks.forEach(track => {
                track.enabled = !track.enabled;
            });
            
            this.isCameraOff = !this.isCameraOff;
            const cameraBtn = document.getElementById('cameraBtn');
            if (cameraBtn) {
                cameraBtn.classList.toggle('active', this.isCameraOff);
                cameraBtn.innerHTML = this.isCameraOff ? 
                    '<i class="fas fa-video-slash"></i>' : 
                    '<i class="fas fa-video"></i>';
            }

            const localVideo = document.getElementById('localVideo');
            if (localVideo) {
                localVideo.style.display = this.isCameraOff ? 'none' : 'block';
            }
        }
    }

    async endCall() {
        try {
            // Notify server
            await fetch(`/end_call/${this.callId}`, { method: 'POST' });
            
            this.cleanup();
            
            // Redirect to home
            window.location.href = '/home';
        } catch (error) {
            console.error('Error ending call:', error);
            this.cleanup();
            window.location.href = '/home';
        }
    }

    cleanup() {
        // Stop all tracks
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => track.stop());
        }
        
        // Close peer connection
        if (this.peerConnection) {
            this.peerConnection.close();
        }
        
        // Leave socket room and disconnect
        if (this.socket) {
            this.socket.emit('leave_call', { call_id: this.callId });
            this.socket.disconnect();
        }
    }

    handleError(message) {
        console.error('WebRTC Error:', message);
        
        // Show error to user
        const errorContainer = document.getElementById('callError');
        if (errorContainer) {
            errorContainer.textContent = message;
            errorContainer.style.display = 'block';
        } else {
            alert(message);
        }

        // End call after error
        setTimeout(() => {
            this.endCall();
        }, 3000);
    }
}

// Screen sharing functionality
class ScreenShare {
    constructor(webrtcCall) {
        this.webrtcCall = webrtcCall;
        this.isSharing = false;
        this.originalStream = null;
    }

    async startScreenShare() {
        try {
            this.originalStream = this.webrtcCall.localStream;
            
            const screenStream = await navigator.mediaDevices.getDisplayMedia({
                video: true,
                audio: true
            });

            // Replace video track
            const videoTrack = screenStream.getVideoTracks()[0];
            const sender = this.webrtcCall.peerConnection.getSenders().find(s => 
                s.track && s.track.kind === 'video'
            );

            if (sender) {
                await sender.replaceTrack(videoTrack);
            }

            this.isSharing = true;

            // Handle screen share end
            videoTrack.addEventListener('ended', () => {
                this.stopScreenShare();
            });

            return true;
        } catch (error) {
            console.error('Error starting screen share:', error);
            return false;
        }
    }

    async stopScreenShare() {
        try {
            if (this.originalStream && this.isSharing) {
                const videoTrack = this.originalStream.getVideoTracks()[0];
                const sender = this.webrtcCall.peerConnection.getSenders().find(s => 
                    s.track && s.track.kind === 'video'
                );

                if (sender && videoTrack) {
                    await sender.replaceTrack(videoTrack);
                }

                this.isSharing = false;
            }
        } catch (error) {
            console.error('Error stopping screen share:', error);
        }
    }
}

// Audio level detection
class AudioLevelDetector {
    constructor(stream) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        this.analyser = this.audioContext.createAnalyser();
        this.source = this.audioContext.createMediaStreamSource(stream);
        this.source.connect(this.analyser);
        
        this.analyser.fftSize = 256;
        this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    }

    getLevel() {
        this.analyser.getByteFrequencyData(this.dataArray);
        let sum = 0;
        for (let i = 0; i < this.dataArray.length; i++) {
            sum += this.dataArray[i];
        }
        return sum / this.dataArray.length;
    }

    startMonitoring(callback) {
        const monitor = () => {
            const level = this.getLevel();
            callback(level);
            requestAnimationFrame(monitor);
        };
        monitor();
    }
}

// Initialize WebRTC when page loads
document.addEventListener('DOMContentLoaded', () => {
    const callContainer = document.querySelector('.call-container');
    if (callContainer) {
        const callId = callContainer.dataset.callId;
        const isInitiator = callContainer.dataset.isInitiator === 'true';
        
        window.webrtcCall = new WebRTCCall(callId, isInitiator);
    }
});
