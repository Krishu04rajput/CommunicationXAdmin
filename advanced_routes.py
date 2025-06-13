"""
Advanced Discord-like Routes for CommunicationX
Includes roles, permissions, threads, webhooks, slash commands, and more
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from models import *
import json
import secrets
import hashlib
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os

advanced = Blueprint('advanced', __name__)

# Permission Constants (Discord-like bitfield permissions)
PERMISSIONS = {
    'CREATE_INSTANT_INVITE': 1 << 0,
    'KICK_MEMBERS': 1 << 1,
    'BAN_MEMBERS': 1 << 2,
    'ADMINISTRATOR': 1 << 3,
    'MANAGE_CHANNELS': 1 << 4,
    'MANAGE_GUILD': 1 << 5,
    'ADD_REACTIONS': 1 << 6,
    'VIEW_AUDIT_LOG': 1 << 7,
    'PRIORITY_SPEAKER': 1 << 8,
    'STREAM': 1 << 9,
    'VIEW_CHANNEL': 1 << 10,
    'SEND_MESSAGES': 1 << 11,
    'SEND_TTS_MESSAGES': 1 << 12,
    'MANAGE_MESSAGES': 1 << 13,
    'EMBED_LINKS': 1 << 14,
    'ATTACH_FILES': 1 << 15,
    'READ_MESSAGE_HISTORY': 1 << 16,
    'MENTION_EVERYONE': 1 << 17,
    'USE_EXTERNAL_EMOJIS': 1 << 18,
    'VIEW_GUILD_INSIGHTS': 1 << 19,
    'CONNECT': 1 << 20,
    'SPEAK': 1 << 21,
    'MUTE_MEMBERS': 1 << 22,
    'DEAFEN_MEMBERS': 1 << 23,
    'MOVE_MEMBERS': 1 << 24,
    'USE_VAD': 1 << 25,
    'CHANGE_NICKNAME': 1 << 26,
    'MANAGE_NICKNAMES': 1 << 27,
    'MANAGE_ROLES': 1 << 28,
    'MANAGE_WEBHOOKS': 1 << 29,
    'MANAGE_EMOJIS_AND_STICKERS': 1 << 30,
    'USE_APPLICATION_COMMANDS': 1 << 31,
    'REQUEST_TO_SPEAK': 1 << 32,
    'MANAGE_EVENTS': 1 << 33,
    'MANAGE_THREADS': 1 << 34,
    'CREATE_PUBLIC_THREADS': 1 << 35,
    'CREATE_PRIVATE_THREADS': 1 << 36,
    'USE_EXTERNAL_STICKERS': 1 << 37,
    'SEND_MESSAGES_IN_THREADS': 1 << 38,
    'USE_EMBEDDED_ACTIVITIES': 1 << 39,
    'MODERATE_MEMBERS': 1 << 40,
}

def has_permission(user_id, server_id, permission):
    """Check if user has specific permission in server"""
    if not user_id or not server_id:
        return False
    
    # Server owner has all permissions
    server = Server.query.get(server_id)
    if server and server.owner_id == user_id:
        return True
    
    membership = ServerMembership.query.filter_by(
        user_id=user_id, server_id=server_id
    ).first()
    
    if not membership:
        return False
    
    # Check role permissions
    if membership.roles:
        role_ids = json.loads(membership.roles)
        roles = Role.query.filter(Role.id.in_(role_ids)).all()
        
        for role in roles:
            if role.permissions & PERMISSIONS.get(permission, 0):
                return True
    
    return False

# Role Management Routes
@advanced.route('/server/<int:server_id>/roles')
@login_required
def manage_roles(server_id):
    """Role management interface"""
    server = Server.query.get_or_404(server_id)
    
    if not has_permission(current_user.id, server_id, 'MANAGE_ROLES'):
        flash('You do not have permission to manage roles.', 'error')
        return redirect(url_for('server_view', server_id=server_id))
    
    roles = Role.query.filter_by(server_id=server_id).order_by(Role.position.desc()).all()
    return render_template('roles/manage.html', server=server, roles=roles, permissions=PERMISSIONS)

@advanced.route('/server/<int:server_id>/roles/create', methods=['POST'])
@login_required
def create_role(server_id):
    """Create new role"""
    if not has_permission(current_user.id, server_id, 'MANAGE_ROLES'):
        return jsonify({'error': 'No permission'}), 403
    
    data = request.get_json()
    role = Role(
        server_id=server_id,
        name=data.get('name', 'New Role'),
        color=data.get('color', '#000000'),
        permissions=int(data.get('permissions', 0)),
        hoist=data.get('hoist', False),
        mentionable=data.get('mentionable', False),
        position=data.get('position', 0)
    )
    
    db.session.add(role)
    db.session.commit()
    
    # Log action
    log_audit_action(server_id, current_user.id, 10, str(role.id), 'Role created')
    
    return jsonify({'success': True, 'role_id': role.id})

@advanced.route('/server/<int:server_id>/roles/<int:role_id>/edit', methods=['POST'])
@login_required
def edit_role(server_id, role_id):
    """Edit existing role"""
    if not has_permission(current_user.id, server_id, 'MANAGE_ROLES'):
        return jsonify({'error': 'No permission'}), 403
    
    role = Role.query.filter_by(id=role_id, server_id=server_id).first_or_404()
    data = request.get_json()
    
    old_values = {
        'name': role.name,
        'color': role.color,
        'permissions': role.permissions
    }
    
    role.name = data.get('name', role.name)
    role.color = data.get('color', role.color)
    role.permissions = int(data.get('permissions', role.permissions))
    role.hoist = data.get('hoist', role.hoist)
    role.mentionable = data.get('mentionable', role.mentionable)
    
    db.session.commit()
    
    # Log changes
    changes = json.dumps({'old': old_values, 'new': data})
    log_audit_action(server_id, current_user.id, 11, str(role.id), 'Role updated', changes)
    
    return jsonify({'success': True})

@advanced.route('/server/<int:server_id>/roles/<int:role_id>/delete', methods=['POST'])
@login_required
def delete_role(server_id, role_id):
    """Delete role"""
    if not has_permission(current_user.id, server_id, 'MANAGE_ROLES'):
        return jsonify({'error': 'No permission'}), 403
    
    role = Role.query.filter_by(id=role_id, server_id=server_id).first_or_404()
    
    # Remove role from all members
    memberships = ServerMembership.query.filter_by(server_id=server_id).all()
    for membership in memberships:
        if membership.roles:
            roles = json.loads(membership.roles)
            if role_id in roles:
                roles.remove(role_id)
                membership.roles = json.dumps(roles)
    
    db.session.delete(role)
    db.session.commit()
    
    log_audit_action(server_id, current_user.id, 12, str(role.id), 'Role deleted')
    
    return jsonify({'success': True})

@advanced.route('/server/<int:server_id>/members/<user_id>/roles', methods=['POST'])
@login_required
def assign_role(server_id, user_id):
    """Assign role to member"""
    if not has_permission(current_user.id, server_id, 'MANAGE_ROLES'):
        return jsonify({'error': 'No permission'}), 403
    
    data = request.get_json()
    role_id = data.get('role_id')
    action = data.get('action', 'add')  # add or remove
    
    membership = ServerMembership.query.filter_by(
        user_id=user_id, server_id=server_id
    ).first_or_404()
    
    roles = json.loads(membership.roles) if membership.roles else []
    
    if action == 'add' and role_id not in roles:
        roles.append(role_id)
    elif action == 'remove' and role_id in roles:
        roles.remove(role_id)
    
    membership.roles = json.dumps(roles)
    db.session.commit()
    
    log_audit_action(server_id, current_user.id, 25, user_id, f'Role {action}ed')
    
    return jsonify({'success': True})

# Thread Management Routes
@advanced.route('/channel/<int:channel_id>/threads/create', methods=['POST'])
@login_required
def create_thread(channel_id):
    """Create new thread"""
    channel = Channel.query.get_or_404(channel_id)
    
    if not has_permission(current_user.id, channel.server_id, 'CREATE_PUBLIC_THREADS'):
        return jsonify({'error': 'No permission'}), 403
    
    data = request.get_json()
    thread = Thread(
        name=data.get('name', 'New Thread'),
        parent_id=channel_id,
        owner_id=current_user.id,
        auto_archive_duration=data.get('auto_archive_duration', 4320)
    )
    
    db.session.add(thread)
    db.session.commit()
    
    return jsonify({'success': True, 'thread_id': thread.id})

@advanced.route('/thread/<int:thread_id>/archive', methods=['POST'])
@login_required
def archive_thread(thread_id):
    """Archive thread"""
    thread = Thread.query.get_or_404(thread_id)
    channel = Channel.query.get(thread.parent_id)
    
    if not (thread.owner_id == current_user.id or 
            has_permission(current_user.id, channel.server_id, 'MANAGE_THREADS')):
        return jsonify({'error': 'No permission'}), 403
    
    thread.archived = True
    thread.archive_timestamp = datetime.now()
    db.session.commit()
    
    return jsonify({'success': True})

# Custom Emoji Management
@advanced.route('/server/<int:server_id>/emojis')
@login_required
def manage_emojis(server_id):
    """Emoji management interface"""
    server = Server.query.get_or_404(server_id)
    
    if not has_permission(current_user.id, server_id, 'MANAGE_EMOJIS_AND_STICKERS'):
        flash('You do not have permission to manage emojis.', 'error')
        return redirect(url_for('server_view', server_id=server_id))
    
    emojis = CustomEmoji.query.filter_by(server_id=server_id).all()
    return render_template('emojis/manage.html', server=server, emojis=emojis)

@advanced.route('/server/<int:server_id>/emojis/upload', methods=['POST'])
@login_required
def upload_emoji(server_id):
    """Upload custom emoji"""
    if not has_permission(current_user.id, server_id, 'MANAGE_EMOJIS_AND_STICKERS'):
        return jsonify({'error': 'No permission'}), 403
    
    if 'emoji_file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['emoji_file']
    name = request.form.get('name', '').strip()
    
    if not name or not file.filename:
        return jsonify({'error': 'Name and file required'}), 400
    
    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        return jsonify({'error': 'Invalid file type'}), 400
    
    # Save file
    filename = secure_filename(f"{name}_{secrets.token_hex(8)}.{file.filename.rsplit('.', 1)[1].lower()}")
    upload_path = os.path.join('static', 'uploads', 'emojis')
    os.makedirs(upload_path, exist_ok=True)
    file_path = os.path.join(upload_path, filename)
    file.save(file_path)
    
    # Create emoji record
    emoji = CustomEmoji(
        server_id=server_id,
        name=name,
        image_url=f"/static/uploads/emojis/{filename}",
        creator_id=current_user.id,
        animated=file.filename.lower().endswith('.gif')
    )
    
    db.session.add(emoji)
    db.session.commit()
    
    log_audit_action(server_id, current_user.id, 60, str(emoji.id), 'Emoji created')
    
    return jsonify({'success': True, 'emoji_id': emoji.id})

# Webhook Management
@advanced.route('/channel/<int:channel_id>/webhooks/create', methods=['POST'])
@login_required
def create_webhook(channel_id):
    """Create webhook for channel"""
    channel = Channel.query.get_or_404(channel_id)
    
    if not has_permission(current_user.id, channel.server_id, 'MANAGE_WEBHOOKS'):
        return jsonify({'error': 'No permission'}), 403
    
    data = request.get_json()
    token = secrets.token_urlsafe(32)
    
    webhook = Webhook(
        channel_id=channel_id,
        server_id=channel.server_id,
        name=data.get('name', 'New Webhook'),
        token=token,
        url=f"/api/webhooks/{token}"
    )
    
    db.session.add(webhook)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'webhook_id': webhook.id,
        'url': webhook.url,
        'token': token
    })

@advanced.route('/api/webhooks/<token>', methods=['POST'])
def execute_webhook(token):
    """Execute webhook"""
    webhook = Webhook.query.filter_by(token=token).first_or_404()
    data = request.get_json()
    
    # Create message from webhook
    message = Message(
        content=data.get('content', ''),
        author_id='webhook',  # Special webhook user
        channel_id=webhook.channel_id,
        message_type='webhook'
    )
    
    db.session.add(message)
    db.session.commit()
    
    return jsonify({'success': True, 'message_id': message.id})

# Slash Command System
@advanced.route('/server/<int:server_id>/commands')
@login_required
def manage_commands(server_id):
    """Manage slash commands"""
    server = Server.query.get_or_404(server_id)
    
    if not has_permission(current_user.id, server_id, 'MANAGE_GUILD'):
        flash('You do not have permission to manage commands.', 'error')
        return redirect(url_for('server_view', server_id=server_id))
    
    commands = SlashCommand.query.filter_by(server_id=server_id).all()
    return render_template('commands/manage.html', server=server, commands=commands)

@advanced.route('/api/interactions', methods=['POST'])
def handle_interaction():
    """Handle slash command interactions"""
    data = request.get_json()
    interaction_type = data.get('type')
    
    if interaction_type == 2:  # APPLICATION_COMMAND
        command_data = data.get('data', {})
        command_name = command_data.get('name')
        
        # Process command based on name
        if command_name == 'ping':
            return jsonify({
                'type': 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                'data': {
                    'content': 'Pong! 🏓'
                }
            })
        elif command_name == 'serverinfo':
            server_id = data.get('guild_id')
            server = Server.query.get(server_id)
            if server:
                return jsonify({
                    'type': 4,
                    'data': {
                        'embeds': [{
                            'title': f'Server Info: {server.name}',
                            'description': server.description or 'No description',
                            'color': 0x5865F2,
                            'fields': [
                                {'name': 'Created', 'value': server.created_at.strftime('%Y-%m-%d'), 'inline': True},
                                {'name': 'Members', 'value': str(len(server.memberships)), 'inline': True}
                            ]
                        }]
                    }
                })
    
    return jsonify({'type': 1})  # PONG

# User Settings Routes
@advanced.route('/settings/profile')
@login_required
def profile_settings():
    """User profile settings"""
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
        db.session.commit()
    
    return render_template('settings/profile.html', user=current_user, settings=settings)

@advanced.route('/settings/profile/update', methods=['POST'])
@login_required
def update_profile_settings():
    """Update user profile settings"""
    data = request.get_json()
    
    # Update user info
    current_user.bio = data.get('bio', current_user.bio)
    current_user.custom_status = data.get('custom_status', current_user.custom_status)
    current_user.accent_color = data.get('accent_color', current_user.accent_color)
    
    # Update settings
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
    
    settings.theme = data.get('theme', settings.theme)
    settings.language = data.get('language', settings.language)
    settings.show_current_game = data.get('show_current_game', settings.show_current_game)
    settings.explicit_content_filter = data.get('explicit_content_filter', settings.explicit_content_filter)
    
    db.session.commit()
    
    return jsonify({'success': True})

@advanced.route('/settings/notifications')
@login_required
def notification_settings():
    """Notification settings"""
    settings = NotificationSettings.query.filter_by(user_id=current_user.id).all()
    servers = Server.query.join(ServerMembership).filter(
        ServerMembership.user_id == current_user.id
    ).all()
    
    return render_template('settings/notifications.html', settings=settings, servers=servers)

# Friend System Routes
@advanced.route('/friends')
@login_required
def friends_list():
    """Friends list interface"""
    friends = db.session.query(Friendship, User).join(
        User, Friendship.friend_id == User.id
    ).filter(
        Friendship.user_id == current_user.id,
        Friendship.status == 'accepted'
    ).all()
    
    pending_sent = db.session.query(Friendship, User).join(
        User, Friendship.friend_id == User.id
    ).filter(
        Friendship.user_id == current_user.id,
        Friendship.status == 'pending'
    ).all()
    
    pending_received = db.session.query(Friendship, User).join(
        User, Friendship.user_id == User.id
    ).filter(
        Friendship.friend_id == current_user.id,
        Friendship.status == 'pending'
    ).all()
    
    return render_template('friends/list.html', 
                         friends=friends, 
                         pending_sent=pending_sent, 
                         pending_received=pending_received)

@advanced.route('/friends/add', methods=['POST'])
@login_required
def add_friend():
    """Send friend request"""
    data = request.get_json()
    username = data.get('username', '').strip()
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    friend = User.query.filter_by(username=username).first()
    if not friend:
        return jsonify({'error': 'User not found'}), 404
    
    if friend.id == current_user.id:
        return jsonify({'error': 'Cannot add yourself'}), 400
    
    # Check if friendship already exists
    existing = Friendship.query.filter(
        ((Friendship.user_id == current_user.id) & (Friendship.friend_id == friend.id)) |
        ((Friendship.user_id == friend.id) & (Friendship.friend_id == current_user.id))
    ).first()
    
    if existing:
        return jsonify({'error': 'Friendship already exists'}), 400
    
    # Create friend request
    friendship = Friendship(
        user_id=current_user.id,
        friend_id=friend.id,
        status='pending'
    )
    
    db.session.add(friendship)
    db.session.commit()
    
    return jsonify({'success': True})

@advanced.route('/friends/<int:friendship_id>/accept', methods=['POST'])
@login_required
def accept_friend(friendship_id):
    """Accept friend request"""
    friendship = Friendship.query.filter_by(
        id=friendship_id,
        friend_id=current_user.id,
        status='pending'
    ).first_or_404()
    
    friendship.status = 'accepted'
    friendship.accepted_at = datetime.now()
    
    # Create reciprocal friendship
    reciprocal = Friendship(
        user_id=current_user.id,
        friend_id=friendship.user_id,
        status='accepted',
        accepted_at=datetime.now()
    )
    
    db.session.add(reciprocal)
    db.session.commit()
    
    return jsonify({'success': True})

@advanced.route('/friends/<int:friendship_id>/decline', methods=['POST'])
@login_required
def decline_friend(friendship_id):
    """Decline friend request"""
    friendship = Friendship.query.filter_by(
        id=friendship_id,
        friend_id=current_user.id,
        status='pending'
    ).first_or_404()
    
    db.session.delete(friendship)
    db.session.commit()
    
    return jsonify({'success': True})

# Scheduled Events
@advanced.route('/server/<int:server_id>/events')
@login_required
def server_events(server_id):
    """Server events interface"""
    server = Server.query.get_or_404(server_id)
    events = ScheduledEvent.query.filter_by(server_id=server_id).order_by(
        ScheduledEvent.scheduled_start_time
    ).all()
    
    return render_template('events/list.html', server=server, events=events)

@advanced.route('/server/<int:server_id>/events/create', methods=['POST'])
@login_required
def create_event(server_id):
    """Create scheduled event"""
    if not has_permission(current_user.id, server_id, 'MANAGE_EVENTS'):
        return jsonify({'error': 'No permission'}), 403
    
    data = request.get_json()
    
    event = ScheduledEvent(
        server_id=server_id,
        creator_id=current_user.id,
        name=data.get('name'),
        description=data.get('description'),
        scheduled_start_time=datetime.fromisoformat(data.get('start_time')),
        scheduled_end_time=datetime.fromisoformat(data.get('end_time')) if data.get('end_time') else None,
        entity_type=data.get('entity_type', 3),  # External by default
        channel_id=data.get('channel_id')
    )
    
    db.session.add(event)
    db.session.commit()
    
    return jsonify({'success': True, 'event_id': event.id})

# Utility Functions
def log_audit_action(server_id, user_id, action_type, target_id=None, reason=None, changes=None):
    """Log action to audit log"""
    log = AuditLog(
        server_id=server_id,
        user_id=user_id,
        action_type=action_type,
        target_id=target_id,
        reason=reason,
        changes=changes
    )
    db.session.add(log)

# Presence Update
@advanced.route('/api/presence/update', methods=['POST'])
@login_required
def update_presence():
    """Update user presence"""
    data = request.get_json()
    
    presence = UserPresence.query.filter_by(user_id=current_user.id).first()
    if not presence:
        presence = UserPresence(user_id=current_user.id)
        db.session.add(presence)
    
    presence.status = data.get('status', 'online')
    presence.activities = json.dumps(data.get('activities', []))
    presence.client_status = json.dumps(data.get('client_status', {}))
    presence.updated_at = datetime.now()
    
    current_user.last_seen = datetime.now()
    
    db.session.commit()
    
    return jsonify({'success': True})

# Server Analytics
@advanced.route('/server/<int:server_id>/analytics')
@login_required
def server_analytics(server_id):
    """Server analytics dashboard"""
    server = Server.query.get_or_404(server_id)
    
    if not has_permission(current_user.id, server_id, 'VIEW_GUILD_INSIGHTS'):
        flash('You do not have permission to view analytics.', 'error')
        return redirect(url_for('server_view', server_id=server_id))
    
    # Gather analytics data
    member_count = ServerMembership.query.filter_by(server_id=server_id).count()
    message_count = Message.query.join(Channel).filter(
        Channel.server_id == server_id
    ).count()
    
    # Messages per day for last 30 days
    thirty_days_ago = datetime.now() - timedelta(days=30)
    daily_messages = db.session.query(
        db.func.date(Message.created_at).label('date'),
        db.func.count(Message.id).label('count')
    ).join(Channel).filter(
        Channel.server_id == server_id,
        Message.created_at >= thirty_days_ago
    ).group_by(
        db.func.date(Message.created_at)
    ).all()
    
    return render_template('analytics/server.html', 
                         server=server,
                         member_count=member_count,
                         message_count=message_count,
                         daily_messages=daily_messages)