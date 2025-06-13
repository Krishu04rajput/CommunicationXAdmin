import streamlit.components.v1 as components
import json

def create_webrtc_component(call_id, user_id, is_initiator=False, call_type="audio"):
    """Create WebRTC component for voice/video calling"""
    
    webrtc_html = f"""
    <div id="webrtc-container-{call_id}" style="width: 100%; height: 400px;">
        <div id="local-video-{call_id}" style="width: 200px; height: 150px; float: right; background: #000;"></div>
        <div id="remote-video-{call_id}" style="width: 100%; height: 100%; background: #000;"></div>
        <div id="call-controls-{call_id}" style="position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%);">
            <button id="mute-btn-{call_id}" onclick="toggleMute('{call_id}')" style="margin: 5px; padding: 10px; background: #f44336; color: white; border: none; border-radius: 5px;">🔇 Mute</button>
            <button id="camera-btn-{call_id}" onclick="toggleCamera('{call_id}')" style="margin: 5px; padding: 10px; background: #2196F3; color: white; border: none; border-radius: 5px;" {"" if call_type == "video" else "display: none;"}>📹 Camera</button>
            <button id="end-btn-{call_id}" onclick="endCall('{call_id}')" style="margin: 5px; padding: 10px; background: #f44336; color: white; border: none; border-radius: 5px;">📞 End</button>
        </div>
    </div>

    <script>
    class WebRTCCall {{
        constructor(callId, userId, isInitiator, callType) {{
            this.callId = callId;
            this.userId = userId;
            this.isInitiator = isInitiator;
            this.callType = callType;
            this.localStream = null;
            this.remoteStream = null;
            this.peerConnection = null;
            this.isMuted = false;
            this.isCameraOff = false;
            
            this.init();
        }}
        
        async init() {{
            try {{
                // Get user media
                const constraints = {{
                    audio: true,
                    video: this.callType === 'video'
                }};
                
                this.localStream = await navigator.mediaDevices.getUserMedia(constraints);
                
                // Setup local video
                const localVideo = document.getElementById(`local-video-${{this.callId}}`);
                if (localVideo && this.callType === 'video') {{
                    const localVideoEl = document.createElement('video');
                    localVideoEl.srcObject = this.localStream;
                    localVideoEl.autoplay = true;
                    localVideoEl.muted = true;
                    localVideoEl.style.width = '100%';
                    localVideoEl.style.height = '100%';
                    localVideo.appendChild(localVideoEl);
                }}
                
                // Setup peer connection
                this.setupPeerConnection();
                
                if (this.isInitiator) {{
                    await this.createOffer();
                }}
                
            }} catch (error) {{
                console.error('Error initializing WebRTC:', error);
                alert('Failed to access camera/microphone. Please check permissions.');
            }}
        }}
        
        setupPeerConnection() {{
            const configuration = {{
                iceServers: [
                    {{ urls: 'stun:stun.l.google.com:19302' }},
                    {{ urls: 'stun:stun1.l.google.com:19302' }}
                ]
            }};
            
            this.peerConnection = new RTCPeerConnection(configuration);
            
            // Add local stream tracks
            this.localStream.getTracks().forEach(track => {{
                this.peerConnection.addTrack(track, this.localStream);
            }});
            
            // Handle remote stream
            this.peerConnection.ontrack = (event) => {{
                this.remoteStream = event.streams[0];
                const remoteVideo = document.getElementById(`remote-video-${{this.callId}}`);
                if (remoteVideo) {{
                    const remoteVideoEl = document.createElement('video');
                    remoteVideoEl.srcObject = this.remoteStream;
                    remoteVideoEl.autoplay = true;
                    remoteVideoEl.style.width = '100%';
                    remoteVideoEl.style.height = '100%';
                    remoteVideo.appendChild(remoteVideoEl);
                }}
            }};
            
            // Handle ICE candidates
            this.peerConnection.onicecandidate = (event) => {{
                if (event.candidate) {{
                    this.sendSignal('ice-candidate', {{
                        candidate: event.candidate
                    }});
                }}
            }};
            
            // Handle connection state changes
            this.peerConnection.onconnectionstatechange = () => {{
                console.log('Connection state:', this.peerConnection.connectionState);
            }};
        }}
        
        async createOffer() {{
            try {{
                const offer = await this.peerConnection.createOffer();
                await this.peerConnection.setLocalDescription(offer);
                
                this.sendSignal('offer', {{
                    offer: offer
                }});
            }} catch (error) {{
                console.error('Error creating offer:', error);
            }}
        }}
        
        async handleOffer(offer) {{
            try {{
                await this.peerConnection.setRemoteDescription(offer);
                const answer = await this.peerConnection.createAnswer();
                await this.peerConnection.setLocalDescription(answer);
                
                this.sendSignal('answer', {{
                    answer: answer
                }});
            }} catch (error) {{
                console.error('Error handling offer:', error);
            }}
        }}
        
        async handleAnswer(answer) {{
            try {{
                await this.peerConnection.setRemoteDescription(answer);
            }} catch (error) {{
                console.error('Error handling answer:', error);
            }}
        }}
        
        async handleIceCandidate(candidate) {{
            try {{
                await this.peerConnection.addIceCandidate(candidate);
            }} catch (error) {{
                console.error('Error handling ICE candidate:', error);
            }}
        }}
        
        sendSignal(type, data) {{
            // Send signaling data to server
            const signalData = {{
                type: type,
                callId: this.callId,
                userId: this.userId,
                data: data
            }};
            
            // In a real implementation, this would send to a WebSocket server
            console.log('Sending signal:', signalData);
            
            // For demo purposes, store in session storage
            const signals = JSON.parse(sessionStorage.getItem('webrtc_signals') || '[]');
            signals.push(signalData);
            sessionStorage.setItem('webrtc_signals', JSON.stringify(signals));
        }}
        
        toggleMute() {{
            if (this.localStream) {{
                const audioTrack = this.localStream.getAudioTracks()[0];
                if (audioTrack) {{
                    audioTrack.enabled = !audioTrack.enabled;
                    this.isMuted = !audioTrack.enabled;
                    
                    const muteBtn = document.getElementById(`mute-btn-${{this.callId}}`);
                    if (muteBtn) {{
                        muteBtn.textContent = this.isMuted ? '🔊 Unmute' : '🔇 Mute';
                        muteBtn.style.background = this.isMuted ? '#4CAF50' : '#f44336';
                    }}
                }}
            }}
        }}
        
        toggleCamera() {{
            if (this.localStream && this.callType === 'video') {{
                const videoTrack = this.localStream.getVideoTracks()[0];
                if (videoTrack) {{
                    videoTrack.enabled = !videoTrack.enabled;
                    this.isCameraOff = !videoTrack.enabled;
                    
                    const cameraBtn = document.getElementById(`camera-btn-${{this.callId}}`);
                    if (cameraBtn) {{
                        cameraBtn.textContent = this.isCameraOff ? '📹 Camera On' : '📹 Camera Off';
                        cameraBtn.style.background = this.isCameraOff ? '#4CAF50' : '#2196F3';
                    }}
                }}
            }}
        }}
        
        endCall() {{
            // Stop local stream
            if (this.localStream) {{
                this.localStream.getTracks().forEach(track => track.stop());
            }}
            
            // Close peer connection
            if (this.peerConnection) {{
                this.peerConnection.close();
            }}
            
            // Notify server about call end
            this.sendSignal('call-ended', {{}});
            
            // Notify parent window
            window.parent.postMessage({{
                type: 'call-ended',
                callId: this.callId
            }}, '*');
        }}
    }}
    
    // Global functions for button handlers
    let callInstance_{call_id} = null;
    
    function toggleMute(callId) {{
        if (callInstance_{call_id}) {{
            callInstance_{call_id}.toggleMute();
        }}
    }}
    
    function toggleCamera(callId) {{
        if (callInstance_{call_id}) {{
            callInstance_{call_id}.toggleCamera();
        }}
    }}
    
    function endCall(callId) {{
        if (callInstance_{call_id}) {{
            callInstance_{call_id}.endCall();
        }}
    }}
    
    // Initialize call when page loads
    document.addEventListener('DOMContentLoaded', function() {{
        callInstance_{call_id} = new WebRTCCall('{call_id}', '{user_id}', {str(is_initiator).lower()}, '{call_type}');
    }});
    
    // Listen for messages from parent window
    window.addEventListener('message', function(event) {{
        if (event.data.type === 'webrtc-signal' && event.data.callId === '{call_id}') {{
            const signal = event.data.signal;
            
            if (callInstance_{call_id}) {{
                switch(signal.type) {{
                    case 'offer':
                        callInstance_{call_id}.handleOffer(signal.data.offer);
                        break;
                    case 'answer':
                        callInstance_{call_id}.handleAnswer(signal.data.answer);
                        break;
                    case 'ice-candidate':
                        callInstance_{call_id}.handleIceCandidate(signal.data.candidate);
                        break;
                }}
            }}
        }}
    }});
    </script>
    """
    
    return components.html(webrtc_html, height=400)