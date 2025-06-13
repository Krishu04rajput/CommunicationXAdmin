import asyncio
import websockets
import json
import logging
from datetime import datetime
from typing import Dict, Set
from call_manager import call_manager, CallStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SignalingServer:
    def __init__(self):
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.user_connections: Dict[str, str] = {}  # user_id -> connection_id
        
    async def register(self, websocket, user_id: str):
        """Register a new WebSocket connection"""
        connection_id = f"{user_id}_{datetime.now().timestamp()}"
        self.connections[connection_id] = websocket
        self.user_connections[user_id] = connection_id
        logger.info(f"User {user_id} connected with connection {connection_id}")
        
        return connection_id
    
    async def unregister(self, connection_id: str, user_id: str):
        """Unregister a WebSocket connection"""
        if connection_id in self.connections:
            del self.connections[connection_id]
        if user_id in self.user_connections:
            del self.user_connections[user_id]
        logger.info(f"User {user_id} disconnected")
    
    async def send_to_user(self, user_id: str, message: dict):
        """Send message to specific user"""
        connection_id = self.user_connections.get(user_id)
        if connection_id and connection_id in self.connections:
            websocket = self.connections[connection_id]
            try:
                await websocket.send(json.dumps(message))
                return True
            except websockets.exceptions.ConnectionClosed:
                await self.unregister(connection_id, user_id)
                return False
        return False
    
    async def handle_call_signal(self, message: dict, sender_id: str):
        """Handle WebRTC signaling messages"""
        call_id = message.get('call_id')
        signal_type = message.get('type')
        data = message.get('data', {})
        
        call = call_manager.get_call(call_id)
        if not call:
            logger.warning(f"Call {call_id} not found")
            return
        
        # Determine recipient
        recipient_id = call.recipient_id if sender_id == call.caller_id else call.caller_id
        
        # Forward signal to recipient
        signal_message = {
            'type': 'webrtc_signal',
            'call_id': call_id,
            'signal_type': signal_type,
            'data': data,
            'sender_id': sender_id
        }
        
        success = await self.send_to_user(recipient_id, signal_message)
        if success:
            logger.info(f"Forwarded {signal_type} signal from {sender_id} to {recipient_id}")
        else:
            logger.warning(f"Failed to send signal to {recipient_id}")
    
    async def handle_call_notification(self, call_id: str, caller_id: str, recipient_id: str, call_type: str, server_id=None):
        """Send call notification to recipient"""
        notification = {
            'type': 'incoming_call',
            'call_id': call_id,
            'caller_id': caller_id,
            'call_type': call_type,
            'server_id': server_id,
            'timestamp': datetime.now().isoformat()
        }
        
        success = await self.send_to_user(recipient_id, notification)
        if success:
            logger.info(f"Sent call notification to {recipient_id}")
        else:
            logger.warning(f"Failed to send call notification to {recipient_id}")
    
    async def handle_call_response(self, message: dict, user_id: str):
        """Handle call accept/decline response"""
        call_id = message.get('call_id')
        response = message.get('response')  # 'accept' or 'decline'
        
        call = call_manager.get_call(call_id)
        if not call:
            return
        
        if response == 'accept':
            call_manager.accept_call(call_id, user_id)
            # Notify caller that call was accepted
            await self.send_to_user(call.caller_id, {
                'type': 'call_accepted',
                'call_id': call_id
            })
        elif response == 'decline':
            call_manager.decline_call(call_id, user_id)
            # Notify caller that call was declined
            await self.send_to_user(call.caller_id, {
                'type': 'call_declined',
                'call_id': call_id
            })
    
    async def handle_message(self, websocket, message_str: str, user_id: str):
        """Handle incoming WebSocket message"""
        try:
            message = json.loads(message_str)
            message_type = message.get('type')
            
            if message_type == 'webrtc_signal':
                await self.handle_call_signal(message, user_id)
            elif message_type == 'call_response':
                await self.handle_call_response(message, user_id)
            elif message_type == 'ping':
                await websocket.send(json.dumps({'type': 'pong'}))
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received from {user_id}")
        except Exception as e:
            logger.error(f"Error handling message from {user_id}: {e}")

# Global signaling server instance
signaling_server = SignalingServer()

async def websocket_handler(websocket, path):
    """WebSocket connection handler"""
    user_id = None
    connection_id = None
    
    try:
        # Wait for authentication message
        auth_message = await websocket.recv()
        auth_data = json.loads(auth_message)
        
        if auth_data.get('type') == 'auth':
            user_id = auth_data.get('user_id')
            if user_id:
                connection_id = await signaling_server.register(websocket, user_id)
                await websocket.send(json.dumps({
                    'type': 'auth_success',
                    'connection_id': connection_id
                }))
                
                # Handle messages
                async for message in websocket:
                    await signaling_server.handle_message(websocket, message, user_id)
            else:
                await websocket.send(json.dumps({
                    'type': 'auth_error',
                    'message': 'User ID required'
                }))
        else:
            await websocket.send(json.dumps({
                'type': 'auth_error',
                'message': 'Authentication required'
            }))
            
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Connection closed for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
    finally:
        if connection_id and user_id:
            await signaling_server.unregister(connection_id, user_id)

def start_signaling_server(host='0.0.0.0', port=8765):
    """Start the signaling server"""
    logger.info(f"Starting signaling server on {host}:{port}")
    return websockets.serve(websocket_handler, host, port)

if __name__ == '__main__':
    # Start the server
    start_server = start_signaling_server()
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()