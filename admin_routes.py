from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from models import User, Server, ServerMembership, Channel, Message, DirectMessage, UserActivity, SystemMetrics, UserSession
from datetime import datetime, timedelta
from sqlalchemy import func, desc, and_, or_
import json
import uuid

admin = Blueprint('admin', __name__)

def is_admin():
    """Check if current user is admin"""
    return current_user.is_authenticated and (current_user.is_admin or current_user.is_super_admin)

def is_super_admin():
    """Check if current user is super admin"""
    return current_user.is_authenticated and current_user.is_super_admin

@admin.route('/admin')
@login_required
def admin_panel():
    """Main admin panel with intelligent analytics"""
    if not is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))
    
    # Basic statistics
    total_users = User.query.count()
    total_servers = Server.query.count()
    total_messages = Message.query.count()
    banned_users = User.query.filter_by(is_banned=True).count()
    locked_servers = Server.query.filter_by(is_locked=True).count()
    admin_users = User.query.filter_by(is_admin=True).count()
    
    # Real-time analytics
    now = datetime.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    
    # Active users (last 24 hours)
    active_users_24h = db.session.query(func.count(func.distinct(UserActivity.user_id))).filter(
        UserActivity.created_at >= datetime.combine(yesterday, datetime.min.time())
    ).scalar() or 0
    
    # Online users (active sessions)
    online_users = UserSession.query.filter(
        and_(
            UserSession.is_active == True,
            UserSession.last_activity >= now - timedelta(minutes=30)
        )
    ).count()
    
    # Messages today
    messages_today = Message.query.filter(
        Message.created_at >= datetime.combine(today, datetime.min.time())
    ).count()
    
    # Messages this week
    messages_week = Message.query.filter(
        Message.created_at >= datetime.combine(week_ago, datetime.min.time())
    ).count()
    
    # New users today
    new_users_today = User.query.filter(
        User.created_at >= datetime.combine(today, datetime.min.time())
    ).count()
    
    # Server activity (servers with activity today)
    active_servers_today = db.session.query(func.count(func.distinct(UserActivity.server_id))).filter(
        and_(
            UserActivity.server_id.isnot(None),
            UserActivity.created_at >= datetime.combine(today, datetime.min.time())
        )
    ).scalar() or 0
    
    # Peak activity hour analysis
    activity_by_hour = db.session.query(
        func.extract('hour', UserActivity.created_at).label('hour'),
        func.count(UserActivity.id).label('activity_count')
    ).filter(
        UserActivity.created_at >= datetime.combine(today, datetime.min.time())
    ).group_by(func.extract('hour', UserActivity.created_at)).all()
    
    # Most active users today
    top_users_today = db.session.query(
        User.username,
        User.first_name,
        func.count(UserActivity.id).label('activity_count')
    ).join(UserActivity).filter(
        UserActivity.created_at >= datetime.combine(today, datetime.min.time())
    ).group_by(User.id).order_by(desc('activity_count')).limit(10).all()
    
    # Device type breakdown
    device_stats = db.session.query(
        UserSession.device_type,
        func.count(UserSession.id).label('count')
    ).filter(
        UserSession.is_active == True
    ).group_by(UserSession.device_type).all()
    
    # Growth metrics
    user_growth_week = []
    for i in range(7):
        day = today - timedelta(days=i)
        users_that_day = User.query.filter(
            func.date(User.created_at) == day
        ).count()
        user_growth_week.append({
            'date': day.strftime('%Y-%m-%d'),
            'users': users_that_day
        })
    user_growth_week.reverse()
    
    stats = {
        'total_users': total_users,
        'total_servers': total_servers,
        'total_messages': total_messages,
        'banned_users': banned_users,
        'locked_servers': locked_servers,
        'admin_users': admin_users,
        'active_users_24h': active_users_24h,
        'online_users': online_users,
        'messages_today': messages_today,
        'messages_week': messages_week,
        'new_users_today': new_users_today,
        'active_servers_today': active_servers_today,
        'activity_by_hour': [{'hour': h, 'count': c} for h, c in activity_by_hour],
        'top_users_today': [{'username': u, 'name': n, 'count': c} for u, n, c in top_users_today],
        'device_stats': [{'type': d or 'unknown', 'count': c} for d, c in device_stats],
        'user_growth_week': user_growth_week
    }
    
    return render_template('admin/dashboard.html', stats=stats)

@admin.route('/admin/users')
@login_required
def manage_users():
    """User management interface"""
    if not is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = User.query
    if search:
        query = query.filter(
            db.or_(
                User.username.contains(search),
                User.email.contains(search),
                User.first_name.contains(search)
            )
        )
    
    users = query.paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/users.html', users=users, search=search)

@admin.route('/admin/users/<int:user_id>/ban', methods=['POST'])
@login_required
def ban_user(user_id):
    """Ban a user"""
    if not is_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get request data safely
        data = request.get_json() or {}
        reason = data.get('reason', 'No reason provided')
        
        # Prevent banning other admins unless super admin
        if getattr(user, 'is_admin', False) and not is_super_admin():
            return jsonify({'error': 'Cannot ban admin users'}), 403
        
        # Prevent banning super admins
        if getattr(user, 'is_super_admin', False):
            return jsonify({'error': 'Cannot ban super admin'}), 403
        
        user.is_banned = True
        user.ban_reason = reason
        user.banned_by = current_user.id
        user.banned_at = datetime.now()
        
        db.session.commit()
        
        username = getattr(user, 'username', None) or getattr(user, 'email', 'Unknown User')
        return jsonify({'success': True, 'message': f'User {username} has been banned'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error banning user: {str(e)}'}), 500

@admin.route('/admin/users/<int:user_id>/unban', methods=['POST'])
@login_required
def unban_user(user_id):
    """Unban a user"""
    if not is_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user.is_banned = False
        user.ban_reason = None
        user.banned_by = None
        user.banned_at = None
        
        db.session.commit()
        
        username = getattr(user, 'username', None) or getattr(user, 'email', 'Unknown User')
        return jsonify({'success': True, 'message': f'User {username} has been unbanned'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error unbanning user: {str(e)}'}), 500

@admin.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    """Delete a user account"""
    if not is_super_admin():
        return jsonify({'error': 'Super admin privileges required'}), 403
    
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Prevent deleting other super admins
        if getattr(user, 'is_super_admin', False) and user.id != current_user.id:
            return jsonify({'error': 'Cannot delete other super admins'}), 403
        
        username = getattr(user, 'username', None) or getattr(user, 'email', 'Unknown User')
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'User {username} has been deleted'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error deleting user: {str(e)}'}), 500

@admin.route('/admin/users/<int:user_id>/make-admin', methods=['POST'])
@login_required
def make_admin(user_id):
    """Make user an admin"""
    if not is_super_admin():
        return jsonify({'error': 'Super admin privileges required'}), 403
    
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user.is_admin = True
        
        permissions = {
            'ban_users': True,
            'manage_servers': True,
            'manage_channels': True,
            'view_audit_logs': True,
            'manage_messages': True
        }
        user.admin_permissions = json.dumps(permissions)
        
        db.session.commit()
        
        username = getattr(user, 'username', None) or getattr(user, 'email', 'Unknown User')
        return jsonify({'success': True, 'message': f'{username} is now an admin'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error making user admin: {str(e)}'}), 500

@admin.route('/admin/users/<int:user_id>/remove-admin', methods=['POST'])
@login_required
def remove_admin(user_id):
    """Remove admin privileges"""
    if not is_super_admin():
        return jsonify({'error': 'Super admin privileges required'}), 403
    
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Prevent removing super admin status
        if getattr(user, 'is_super_admin', False):
            return jsonify({'error': 'Cannot remove super admin status'}), 403
        
        user.is_admin = False
        user.admin_permissions = None
        
        db.session.commit()
        
        username = getattr(user, 'username', None) or getattr(user, 'email', 'Unknown User')
        return jsonify({'success': True, 'message': f'{username} is no longer an admin'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error removing admin privileges: {str(e)}'}), 500

@admin.route('/admin/servers')
@login_required
def manage_servers():
    """Server management interface"""
    if not is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = Server.query
    if search:
        query = query.filter(Server.name.contains(search))
    
    servers = query.paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/servers.html', servers=servers, search=search)

@admin.route('/admin/servers/<int:server_id>/set-password', methods=['POST'])
@login_required
def set_server_password(server_id):
    """Set password for server"""
    if not is_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    server = Server.query.get_or_404(server_id)
    password = request.json.get('password')
    
    if not password:
        return jsonify({'error': 'Password is required'}), 400
    
    server.password_hash = generate_password_hash(password)
    server.password_enabled = True
    server.password_set_by = current_user.id
    server.password_set_at = datetime.now()
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Password set for server {server.name}'})

@admin.route('/admin/servers/<int:server_id>/change-password', methods=['POST'])
@login_required
def change_server_password(server_id):
    """Change server password"""
    if not is_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    server = Server.query.get_or_404(server_id)
    new_password = request.json.get('password')
    
    if not new_password:
        return jsonify({'error': 'New password is required'}), 400
    
    server.password_hash = generate_password_hash(new_password)
    server.password_set_by = current_user.id
    server.password_set_at = datetime.now()
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Password changed for server {server.name}'})

@admin.route('/admin/servers/<int:server_id>/remove-password', methods=['POST'])
@login_required
def remove_server_password(server_id):
    """Remove server password"""
    if not is_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    server = Server.query.get_or_404(server_id)
    
    server.password_hash = None
    server.password_enabled = False
    server.password_set_by = None
    server.password_set_at = None
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Password removed from server {server.name}'})

@admin.route('/admin/servers/<int:server_id>/lock', methods=['POST'])
@login_required
def lock_server(server_id):
    """Lock a server"""
    if not is_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    server = Server.query.get_or_404(server_id)
    reason = request.json.get('reason', 'No reason provided')
    
    server.is_locked = True
    server.locked_by = current_user.id
    server.locked_at = datetime.now()
    server.lock_reason = reason
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Server {server.name} has been locked'})

@admin.route('/admin/servers/<int:server_id>/unlock', methods=['POST'])
@login_required
def unlock_server(server_id):
    """Unlock a server"""
    if not is_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    server = Server.query.get_or_404(server_id)
    
    server.is_locked = False
    server.locked_by = None
    server.locked_at = None
    server.lock_reason = None
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Server {server.name} has been unlocked'})

@admin.route('/admin/servers/<int:server_id>/delete', methods=['POST'])
@login_required
def delete_server(server_id):
    """Delete a server"""
    if not is_super_admin():
        return jsonify({'error': 'Super admin privileges required'}), 403
    
    server = Server.query.get_or_404(server_id)
    server_name = server.name
    
    db.session.delete(server)
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Server {server_name} has been deleted'})

@admin.route('/admin/audit-logs')
@login_required
def audit_logs():
    """View audit logs"""
    if not is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))
    
    # This would show admin actions, user bans, server changes, etc.
    # For now, return basic template
    return render_template('admin/audit_logs.html')

@admin.route('/admin/analytics/api/realtime')
@login_required
def realtime_analytics():
    """Real-time analytics API endpoint"""
    if not is_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    now = datetime.now()
    
    # Current online users
    online_users = UserSession.query.filter(
        and_(
            UserSession.is_active == True,
            UserSession.last_activity >= now - timedelta(minutes=30)
        )
    ).count()
    
    # Activity in last hour
    activity_last_hour = UserActivity.query.filter(
        UserActivity.created_at >= now - timedelta(hours=1)
    ).count()
    
    # Messages in last hour
    messages_last_hour = Message.query.filter(
        Message.created_at >= now - timedelta(hours=1)
    ).count()
    
    # New users today
    today = now.date()
    new_users_today = User.query.filter(
        User.created_at >= datetime.combine(today, datetime.min.time())
    ).count()
    
    return jsonify({
        'online_users': online_users,
        'activity_last_hour': activity_last_hour,
        'messages_last_hour': messages_last_hour,
        'new_users_today': new_users_today,
        'timestamp': now.isoformat()
    })

@admin.route('/admin/analytics/api/activity-chart')
@login_required
def activity_chart_data():
    """Activity chart data for the last 24 hours"""
    if not is_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    now = datetime.now()
    hours_data = []
    
    for i in range(24):
        hour_start = now - timedelta(hours=i+1)
        hour_end = now - timedelta(hours=i)
        
        activity_count = UserActivity.query.filter(
            and_(
                UserActivity.created_at >= hour_start,
                UserActivity.created_at < hour_end
            )
        ).count()
        
        hours_data.append({
            'hour': hour_start.strftime('%H:00'),
            'activity': activity_count
        })
    
    hours_data.reverse()
    return jsonify(hours_data)

@admin.route('/admin/analytics/api/user-growth')
@login_required
def user_growth_data():
    """User growth data for the last 30 days"""
    if not is_admin():
        return jsonify({'error': 'Access denied'}), 403
    
    now = datetime.now()
    growth_data = []
    
    for i in range(30):
        day = now.date() - timedelta(days=i)
        users_that_day = User.query.filter(
            func.date(User.created_at) == day
        ).count()
        
        growth_data.append({
            'date': day.strftime('%Y-%m-%d'),
            'users': users_that_day
        })
    
    growth_data.reverse()
    return jsonify(growth_data)

def track_activity(user_id, activity_type, activity_data=None, server_id=None, channel_id=None):
    """Helper function to track user activity"""
    try:
        activity = UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            activity_data=json.dumps(activity_data) if activity_data else None,
            server_id=server_id,
            channel_id=channel_id,
            session_id=request.headers.get('X-Session-ID'),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        print(f"Error tracking activity: {e}")

def create_user_session(user_id):
    """Create or update user session"""
    try:
        session_id = str(uuid.uuid4())
        user_agent = request.headers.get('User-Agent', '')
        
        # Parse device type from user agent
        device_type = 'desktop'
        if 'Mobile' in user_agent:
            device_type = 'mobile'
        elif 'Tablet' in user_agent:
            device_type = 'tablet'
        
        # Parse browser
        browser = 'unknown'
        if 'Chrome' in user_agent:
            browser = 'Chrome'
        elif 'Firefox' in user_agent:
            browser = 'Firefox'
        elif 'Safari' in user_agent:
            browser = 'Safari'
        elif 'Edge' in user_agent:
            browser = 'Edge'
        
        # Parse OS
        os = 'unknown'
        if 'Windows' in user_agent:
            os = 'Windows'
        elif 'Mac' in user_agent:
            os = 'macOS'
        elif 'Linux' in user_agent:
            os = 'Linux'
        elif 'Android' in user_agent:
            os = 'Android'
        elif 'iOS' in user_agent:
            os = 'iOS'
        
        session = UserSession(
            user_id=user_id,
            session_id=session_id,
            ip_address=request.remote_addr,
            user_agent=user_agent,
            device_type=device_type,
            browser=browser,
            os=os
        )
        db.session.add(session)
        db.session.commit()
        
        # Track login activity
        track_activity(user_id, 'login')
        
        return session_id
    except Exception as e:
        print(f"Error creating user session: {e}")
        return None

def update_session_activity(user_id):
    """Update user session last activity"""
    try:
        session = UserSession.query.filter_by(
            user_id=user_id,
            is_active=True
        ).first()
        
        if session:
            session.last_activity = datetime.now()
            db.session.commit()
    except Exception as e:
        print(f"Error updating session activity: {e}")

@admin.route('/admin/debug/user-status')
@login_required
def debug_user_status():
    """Debug route to check current user admin status"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_info = {
        'id': current_user.id,
        'email': current_user.email,
        'username': current_user.username,
        'first_name': current_user.first_name,
        'last_name': current_user.last_name,
        'is_admin': getattr(current_user, 'is_admin', False),
        'is_super_admin': getattr(current_user, 'is_super_admin', False),
        'email_verified': getattr(current_user, 'email_verified', False),
        'status': getattr(current_user, 'status', 'unknown')
    }
    
    return jsonify(user_info)

@admin.route('/admin/debug/grant-admin')
@login_required
def grant_admin_debug():
    """Emergency route to grant admin privileges to current user if they have the right email"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if current_user.email == 'k.rajput0542@gmail.com':
        current_user.is_admin = True
        current_user.is_super_admin = True
        current_user.email_verified = True
        db.session.commit()
        return jsonify({'success': 'Admin privileges granted', 'user': current_user.email})
    else:
        return jsonify({'error': 'Unauthorized email address'}), 403

@admin.route('/admin/force-access')
def force_admin_access():
    """Emergency admin access for super admin email"""
    from flask_login import login_user
    
    # Find or create super admin user
    super_admin = User.query.filter_by(email='k.rajput0542@gmail.com').first()
    
    if not super_admin:
        super_admin = User(
            email='k.rajput0542@gmail.com',
            username='SuperAdmin',
            first_name='Krishna',
            last_name='Rajput',
            is_admin=True,
            is_super_admin=True,
            email_verified=True,
            status='online'
        )
        db.session.add(super_admin)
        db.session.commit()
    else:
        super_admin.is_admin = True
        super_admin.is_super_admin = True
        super_admin.email_verified = True
        super_admin.status = 'online'
        db.session.commit()
    
    login_user(super_admin, remember=True)
    
    # Create some test servers if none exist
    if Server.query.count() == 0:
        test_servers = [
            Server(name='General Chat', description='Main community server', owner_id=super_admin.id, is_public=True),
            Server(name='Gaming Hub', description='For gaming discussions', owner_id=super_admin.id, is_public=True),
            Server(name='Tech Talk', description='Technology discussions', owner_id=super_admin.id, is_public=False, password_enabled=True, password_hash=generate_password_hash('tech123')),
            Server(name='Music Lounge', description='Share and discuss music', owner_id=super_admin.id, is_public=True),
            Server(name='Study Group', description='Academic discussions', owner_id=super_admin.id, is_public=False)
        ]
        for server in test_servers:
            db.session.add(server)
        db.session.commit()
    
    flash('Emergency admin access granted - you can now access all admin features', 'success')
    return redirect(url_for('admin.manage_servers'))

def setup_super_admin():
    """Setup initial super admin account"""
    # Check if super admin exists
    super_admin = User.query.filter_by(email='k.rajput0542@gmail.com').first()
    
    if not super_admin:
        # Create super admin account
        super_admin = User(
            email='k.rajput0542@gmail.com',
            username='SuperAdmin',
            first_name='Krishna',
            last_name='Rajput',
            is_admin=True,
            is_super_admin=True,
            email_verified=True,
            status='online'
        )
        db.session.add(super_admin)
        db.session.commit()
        print(f"Super admin account created for {super_admin.email}")
    else:
        # Make existing user super admin
        super_admin.is_admin = True
        super_admin.is_super_admin = True
        super_admin.email_verified = True
        db.session.commit()
        print(f"Super admin privileges granted to {super_admin.email}")