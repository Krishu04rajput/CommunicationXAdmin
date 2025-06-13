from flask_socketio import emit, join_room, leave_room, disconnect
from flask_login import current_user
from app import socketio, db
from models import Call, Message, DirectMessage, MessageReadStatus, User
from datetime import datetime
import logging

@socketio.on('join_call')
def on_join_call(data):
    if not current_user.is_authenticated:
        disconnect()
        return
    
    try:
        call_id = data.get('call_id')
        if not call_id:
            return
        
        # Verify user has access to this call
        call = Call.query.get(call_id)
        if not call or (call.caller_id != current_user.id and call.recipient_id != current_user.id):
            disconnect()
            return
        
        join_room(f"call_{call_id}")
        emit('user_joined', {'user_id': current_user.id}, to=f"call_{call_id}")
    except Exception as e:
        logging.error(f"Error in join_call: {e}")
        disconnect()

@socketio.on('leave_call')
def on_leave_call(data):
    call_id = data['call_id']
    leave_room(f"call_{call_id}")
    emit('user_left', {'user_id': current_user.id}, to=f"call_{call_id}")

@socketio.on('webrtc_offer')
def on_webrtc_offer(data):
    if not current_user.is_authenticated:
        disconnect()
        return
    
    call_id = data.get('call_id')
    offer = data.get('offer')
    
    if call_id and offer:
        emit('webrtc_offer', {
            'call_id': call_id,
            'offer': offer,
            'sender_id': current_user.id
        }, to=f"call_{call_id}", include_self=False)

@socketio.on('webrtc_answer')
def on_webrtc_answer(data):
    if not current_user.is_authenticated:
        disconnect()
        return
    
    call_id = data.get('call_id')
    answer = data.get('answer')
    
    if call_id and answer:
        emit('webrtc_answer', {
            'call_id': call_id,
            'answer': answer,
            'sender_id': current_user.id
        }, to=f"call_{call_id}", include_self=False)

@socketio.on('webrtc_ice_candidate')
def on_webrtc_ice_candidate(data):
    if not current_user.is_authenticated:
        disconnect()
        return
    
    call_id = data.get('call_id')
    candidate = data.get('candidate')
    
    if call_id and candidate:
        emit('webrtc_ice_candidate', {
            'call_id': call_id,
            'candidate': candidate,
            'sender_id': current_user.id
        }, to=f"call_{call_id}", include_self=False)

# Message Status and Typing Events

@socketio.on('typing')
def on_typing(data):
    """Handle typing indicators"""
    if not current_user.is_authenticated:
        return
    
    channel_id = data.get('channel_id')
    if not channel_id:
        return
    
    emit('user_typing', {
        'user_id': current_user.id,
        'username': current_user.username,
        'channel_id': channel_id
    }, to=f"channel_{channel_id}", include_self=False)

@socketio.on('stop_typing')
def on_stop_typing(data):
    """Handle stop typing indicators"""
    if not current_user.is_authenticated:
        return
    
    channel_id = data.get('channel_id')
    if not channel_id:
        return
    
    emit('user_stopped_typing', {
        'user_id': current_user.id,
        'channel_id': channel_id
    }, to=f"channel_{channel_id}", include_self=False)

@socketio.on('mark_message_read')
def on_mark_message_read(data):
    """Mark message as read and update status"""
    if not current_user.is_authenticated:
        return
    
    try:
        message_id = data.get('message_id')
        message_type = data.get('type', 'channel')
        
        if not message_id:
            return
        
        now = datetime.now()
        
        if message_type == 'dm':
            dm = DirectMessage.query.get(message_id)
            if dm and dm.recipient_id == current_user.id and not dm.read_at:
                dm.read_at = now
                dm.status = 'read'
                db.session.commit()
                
                emit('message_status_update', {
                    'message_id': message_id,
                    'status': 'read',
                    'timestamp': now.isoformat(),
                    'read_by': [{
                        'user_id': current_user.id,
                        'username': current_user.username,
                        'avatar': current_user.profile_image_url
                    }]
                }, to=f"user_{dm.sender_id}")
                
        else:
            message = Message.query.get(message_id)
            if not message:
                return
            
            existing_read = MessageReadStatus.query.filter_by(
                message_id=message_id,
                user_id=current_user.id
            ).first()
            
            if not existing_read:
                read_status = MessageReadStatus(
                    message_id=message_id,
                    user_id=current_user.id,
                    read_at=now
                )
                db.session.add(read_status)
                
                read_by_users = db.session.query(MessageReadStatus, User).join(
                    User, MessageReadStatus.user_id == User.id
                ).filter(MessageReadStatus.message_id == message_id).all()
                
                read_by = [{
                    'user_id': user.id,
                    'username': user.username,
                    'avatar': user.profile_image_url
                } for _, user in read_by_users]
                
                if len(read_by) == 1 and message.status != 'read':
                    message.status = 'read'
                    message.read_at = now
                
                db.session.commit()
                
                emit('message_status_update', {
                    'message_id': message_id,
                    'status': 'read',
                    'timestamp': now.isoformat(),
                    'read_by': read_by
                }, to=f"channel_{message.channel_id}")
                
    except Exception as e:
        logging.error(f"Error marking message as read: {e}")
        db.session.rollback()

@socketio.on('join_channel')
def on_join_channel(data):
    """Join a channel room for real-time updates"""
    if not current_user.is_authenticated:
        return
    
    channel_id = data.get('channel_id')
    if channel_id:
        join_room(f"channel_{channel_id}")

@socketio.on('connect')
def on_connect():
    if current_user.is_authenticated:
        join_room(f"user_{current_user.id}")
        current_user.status = 'online'
        current_user.last_seen = datetime.now()
        db.session.commit()
        emit('connected', {'user_id': current_user.id})

@socketio.on('disconnect')
def on_disconnect():
    if current_user.is_authenticated:
        leave_room(f"user_{current_user.id}")
        current_user.status = 'away'
        current_user.last_seen = datetime.now()
        db.session.commit()
        emit('disconnected', {'user_id': current_user.id})
