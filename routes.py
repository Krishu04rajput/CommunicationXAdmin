from flask import session, render_template, request, redirect, url_for, flash, jsonify, abort, send_file
from flask_login import current_user, login_user
from app import app, db, limiter
from replit_auth import require_login, make_replit_blueprint
from models import User, Server, Channel, Message, DirectMessage, ServerMembership, Call, CallMessage, Voicemail, Invitation, SharedFile, MessageReaction, MessageReport
from datetime import datetime
import bleach
import hashlib
import uuid
import os
import base64
import logging
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import io

app.register_blueprint(make_replit_blueprint(), url_prefix="/auth")

# Register admin routes
try:
    from admin_routes import admin, setup_super_admin
    app.register_blueprint(admin)
    print("Admin routes registered successfully")
    
    # Set up super admin on startup
    with app.app_context():
        setup_super_admin()
except Exception as e:
    print(f"Error registering admin routes: {e}")

def sanitize_input(text, max_length=1000):
    """Sanitize and validate user input"""
    if not text:
        return ""
    # Strip whitespace and limit length
    text = text.strip()[:max_length]
    # Allow basic HTML tags for messages
    allowed_tags = ['b', 'i', 'u', 'em', 'strong', 'br']
    return bleach.clean(text, tags=allowed_tags, strip=True)

@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route('/')
def index():
    try:
        # Initialize database on first request only
        from app import init_database
        init_database()
        
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        return render_template('splash.html')
    except Exception as e:
        logging.error(f"Error in index route: {e}")
        return f"<h1>CommunicationX</h1><p>Application starting up...</p><p><a href='/landing'>Continue to Landing Page</a></p>"

@app.route('/landing')
def landing():
    return render_template('landing.html')

@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/custom_auth', methods=['POST'])
def custom_auth():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    
    if not username or not email or not password:
        flash('All fields are required', 'error')
        return redirect(url_for('login'))
    
    try:
        # First check if a user exists with this email
        existing_user_by_email = User.query.filter_by(email=email).first()
        
        if existing_user_by_email:
            # User exists with this email - try to login
            if existing_user_by_email.password_hash and check_password_hash(existing_user_by_email.password_hash, password):
                # Check if this is the super admin
                if email == 'k.rajput0542@gmail.com':
                    existing_user_by_email.is_admin = True
                    existing_user_by_email.is_super_admin = True
                    existing_user_by_email.email_verified = True
                    db.session.commit()
                
                login_user(existing_user_by_email, remember=True)
                flash(f'Welcome back, {existing_user_by_email.username}!', 'success')
                return redirect(url_for('home'))
            else:
                flash('Invalid password for this email', 'error')
                return redirect(url_for('login'))
        
        # Check if username is already taken by another user
        existing_user_by_username = User.query.filter_by(username=username).first()
        if existing_user_by_username:
            flash('Username already exists. Please choose a different username.', 'error')
            return redirect(url_for('login'))
        
        # Create new user account
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            first_name=username.split('_')[0].capitalize() if '_' in username else username.capitalize(),
            email_verified=True,
            status='online'
        )
        
        # Check if this is the super admin email
        if email == 'k.rajput0542@gmail.com':
            new_user.is_admin = True
            new_user.is_super_admin = True
            flash('Super admin account created successfully!', 'success')
        
        db.session.add(new_user)
        db.session.commit()
        
        # Auto-join public servers
        from models import ServerMembership
        public_servers = Server.query.filter_by(is_public=True).all()
        for server in public_servers:
            membership = ServerMembership(user_id=new_user.id, server_id=server.id)
            db.session.add(membership)
        
        db.session.commit()
        
        # Log in the new user
        login_user(new_user, remember=True)
        flash(f'Account created successfully! Welcome to CommunicationX, {username}!', 'success')
        return redirect(url_for('home'))
            
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error in custom_auth: {e}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def custom_login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def custom_signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        first_name = sanitize_input(request.form.get('first_name', ''), max_length=50)
        last_name = sanitize_input(request.form.get('last_name', ''), max_length=50)
        username = sanitize_input(request.form.get('username', ''), max_length=64)
        email = sanitize_input(request.form.get('email', ''), max_length=255)
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not all([first_name, last_name, username, email, password]):
            flash('All fields are required.', 'error')
            return render_template('signup.html')
        
        if len(username) < 3:
            flash('Username must be at least 3 characters long.', 'error')
            return render_template('signup.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('signup.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('signup.html')
        
        # Check if user exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            flash('Username or email already exists.', 'error')
            return render_template('signup.html')
        
        try:
            # Create new user
            user_id = str(uuid.uuid4())
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            user = User()
            user.id = user_id
            user.first_name = first_name
            user.last_name = last_name
            user.username = username
            user.email = email
            user.password_hash = password_hash
            
            db.session.add(user)
            db.session.flush()  # Get user ID before committing
            
            # Check if there's an invitation code in session
            invitation_code = session.get('invitation_code')
            if invitation_code:
                invitation = Invitation.query.filter_by(code=invitation_code).first()
                if invitation and invitation.uses_left > 0:
                    invitation.uses_left -= 1
                    db.session.add(invitation)
                    session.pop('invitation_code', None)  # Remove from session
            
            # Auto-add to public servers
            auto_add_user_to_servers(user)
            
            db.session.commit()
            
            # Log in the user
            login_user(user)
            
            flash('Account created successfully!', 'success')
            return redirect(url_for('home'))
        
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error creating account. Please try again.', 'error')
            return render_template('signup.html')
    
    return render_template('signup.html')

@app.route('/custom_login', methods=['POST'])
@limiter.limit("5 per minute")
def handle_custom_login():
    username = sanitize_input(request.form.get('username', ''), max_length=64)
    email = sanitize_input(request.form.get('email', ''), max_length=255)
    password = request.form.get('password', '')
    
    if not password:
        flash('Password is required.', 'error')
        return redirect(url_for('custom_login'))
    
    # Find user by username or email
    user = None
    if username:
        user = User.query.filter_by(username=username).first()
    elif email:
        user = User.query.filter_by(email=email).first()
    
    if not user:
        flash('Invalid credentials.', 'error')
        return redirect(url_for('custom_login'))
    
    # For now, we'll use a simple password check
    # In production, you should use proper password hashing like bcrypt
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    if hasattr(user, 'password_hash') and user.password_hash == password_hash:
        login_user(user)
        return redirect(url_for('home'))
    else:
        flash('Invalid credentials.', 'error')
        return redirect(url_for('custom_login'))

@app.route('/home')
@require_login
def home():
    # Get user's servers
    user_servers = db.session.query(Server).join(ServerMembership).filter(
        ServerMembership.user_id == current_user.id
    ).all()
    
    # Get owned servers
    owned_servers = Server.query.filter_by(owner_id=current_user.id).all()
    
    # Combine and deduplicate
    all_servers = list({server.id: server for server in user_servers + owned_servers}.values())
    
    return render_template('home.html', servers=all_servers)

@app.route('/server/<int:server_id>')
@require_login
def server_view(server_id):
    server = Server.query.get_or_404(server_id)
    
    # Check if user has access to this server
    is_member = ServerMembership.query.filter_by(
        user_id=current_user.id, 
        server_id=server_id
    ).first() is not None
    
    is_owner = server.owner_id == current_user.id
    
    if not (is_member or is_owner):
        flash('You do not have access to this server.', 'error')
        return redirect(url_for('home'))
    
    # Get first channel or create one if none exist
    channel = server.channels[0] if server.channels else None
    if not channel and is_owner:
        channel = Channel(name='general', server_id=server_id)
        db.session.add(channel)
        db.session.commit()
    
    messages = []
    if channel:
        messages = Message.query.filter_by(channel_id=channel.id).order_by(Message.created_at.desc()).limit(50).all()
        messages.reverse()
    
    members = db.session.query(User).join(ServerMembership).filter(
        ServerMembership.server_id == server_id
    ).all()
    
    return render_template('server.html', 
                         server=server, 
                         channel=channel, 
                         messages=messages, 
                         members=members,
                         is_owner=is_owner)

@app.route('/server/<int:server_id>/send_message', methods=['POST'])
@require_login
@limiter.limit("30 per minute")
def send_message(server_id):
    server = Server.query.get_or_404(server_id)
    content = sanitize_input(request.form.get('message', ''), max_length=2000)
    
    if not content or len(content.strip()) == 0:
        flash('Message cannot be empty.', 'error')
        return redirect(url_for('server_view', server_id=server_id))
    
    if len(content) > 2000:
        flash('Message is too long. Maximum 2000 characters allowed.', 'error')
        return redirect(url_for('server_view', server_id=server_id))
    
    # Check access
    is_member = ServerMembership.query.filter_by(
        user_id=current_user.id, 
        server_id=server_id
    ).first() is not None
    
    is_owner = server.owner_id == current_user.id
    
    if not (is_member or is_owner):
        flash('You do not have access to this server.', 'error')
        return redirect(url_for('home'))
    
    # Get or create general channel
    channel = server.channels[0] if server.channels else None
    if not channel:
        channel = Channel(name='general', server_id=server_id)
        db.session.add(channel)
        db.session.commit()
    
    try:
        message = Message(
            content=content,
            author_id=current_user.id,
            channel_id=channel.id
        )
        db.session.add(message)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Error sending message: {e}")
        flash('Error sending message. Please try again.', 'error')
    
    return redirect(url_for('server_view', server_id=server_id))

@app.route('/create_server', methods=['POST'])
@require_login
@limiter.limit("5 per hour")
def create_server():
    logging.info(f"Create server request from user {current_user.id}")
    logging.info(f"Form data: {request.form}")
    
    name = sanitize_input(request.form.get('server_name', ''), max_length=100)
    description = sanitize_input(request.form.get('server_description', ''), max_length=500)
    
    logging.info(f"Processed name: '{name}', description: '{description}'")
    
    if not name or len(name.strip()) < 3:
        flash('Server name must be at least 3 characters long.', 'error')
        return redirect(url_for('home'))
    
    if len(name) > 100:
        flash('Server name is too long. Maximum 100 characters allowed.', 'error')
        return redirect(url_for('home'))
    
    # Check for duplicate server names (optional - remove if you want to allow duplicates)
    existing_server = Server.query.filter_by(name=name.strip(), owner_id=current_user.id).first()
    if existing_server:
        flash('You already have a server with this name.', 'error')
        return redirect(url_for('home'))
    
    try:
        # Create the server
        server = Server(
            name=name.strip(),
            description=description.strip() if description else None,
            owner_id=current_user.id,
            is_public=False  # New servers are private by default
        )
        db.session.add(server)
        db.session.flush()  # Get server ID before committing
        
        logging.info(f"Created server with ID: {server.id}")
        
        # Create default general channel
        channel = Channel(name='general', server_id=server.id)
        db.session.add(channel)
        db.session.flush()
        
        logging.info(f"Created channel with ID: {channel.id}")
        
        # Add owner as member
        membership = ServerMembership(
            user_id=current_user.id,
            server_id=server.id
        )
        db.session.add(membership)
        
        # Commit all changes together
        db.session.commit()
        
        logging.info(f"Server '{name}' created successfully by user {current_user.id}")
        flash(f'Server "{name}" created successfully!', 'success')
        return redirect(url_for('server_view', server_id=server.id))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating server: {str(e)}")
        logging.error(f"Server name: '{name}', Description: '{description}', Owner ID: {current_user.id}")
        flash('Error creating server. Please try again.', 'error')
        return redirect(url_for('home'))

@app.route('/server/<int:server_id>/add_member', methods=['POST'])
@require_login
def add_member(server_id):
    server = Server.query.get_or_404(server_id)
    
    if server.owner_id != current_user.id:
        flash('Only the server owner can add members.', 'error')
        return redirect(url_for('server_view', server_id=server_id))
    
    username = request.form.get('username', '').strip()
    if not username:
        flash('Username is required.', 'error')
        return redirect(url_for('server_view', server_id=server_id))
    
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('server_view', server_id=server_id))
    
    # Check if already a member
    existing_membership = ServerMembership.query.filter_by(
        user_id=user.id,
        server_id=server_id
    ).first()
    
    if existing_membership:
        flash('User is already a member of this server.', 'warning')
        return redirect(url_for('server_view', server_id=server_id))
    
    membership = ServerMembership(
        user_id=user.id,
        server_id=server_id
    )
    db.session.add(membership)
    db.session.commit()
    
    flash(f'User {username} added to server successfully!', 'success')
    return redirect(url_for('server_view', server_id=server_id))

@app.route('/direct_messages')
@require_login
def direct_messages():
    # Get all users who have had conversations with current user
    conversations = db.session.query(User).join(
        DirectMessage,
        (DirectMessage.sender_id == User.id) | (DirectMessage.recipient_id == User.id)
    ).filter(
        (DirectMessage.sender_id == current_user.id) | (DirectMessage.recipient_id == current_user.id),
        User.id != current_user.id
    ).distinct().all()
    
    # Get all users for potential new conversations
    all_users = User.query.filter(User.id != current_user.id).all()
    
    return render_template('direct_messages.html', 
                         conversations=conversations, 
                         all_users=all_users)

@app.route('/dm/<user_id>')
@require_login
def dm_conversation(user_id):
    other_user = User.query.get_or_404(user_id)
    
    # Get messages between current user and other user
    messages = DirectMessage.query.filter(
        ((DirectMessage.sender_id == current_user.id) & (DirectMessage.recipient_id == user_id)) |
        ((DirectMessage.sender_id == user_id) & (DirectMessage.recipient_id == current_user.id))
    ).order_by(DirectMessage.created_at.desc()).limit(50).all()
    
    messages.reverse()
    
    # Mark messages as read
    DirectMessage.query.filter(
        DirectMessage.sender_id == user_id,
        DirectMessage.recipient_id == current_user.id,
        DirectMessage.read_at == None
    ).update({DirectMessage.read_at: datetime.now()})
    db.session.commit()
    
    return render_template('direct_messages.html', 
                         other_user=other_user, 
                         messages=messages,
                         all_users=User.query.filter(User.id != current_user.id).all())

@app.route('/send_dm/<user_id>', methods=['POST'])
@require_login
def send_dm(user_id):
    other_user = User.query.get_or_404(user_id)
    content = request.form.get('message', '').strip()
    
    if not content:
        flash('Message cannot be empty.', 'error')
        return redirect(url_for('dm_conversation', user_id=user_id))
    
    dm = DirectMessage(
        content=content,
        sender_id=current_user.id,
        recipient_id=user_id,
        status='sent'  # Set initial status as sent
    )
    db.session.add(dm)
    db.session.commit()
    
    # Emit real-time status update
    from socket_events import socketio
    socketio.emit('message_status_update', {
        'message_id': dm.id,
        'status': 'sent',
        'timestamp': dm.created_at.isoformat()
    }, to=f'user_{user_id}')
    
    return redirect(url_for('dm_conversation', user_id=user_id))

@app.route('/call/<user_id>/<call_type>')
@require_login
def initiate_call(user_id, call_type):
    other_user = User.query.get_or_404(user_id)
    
    if call_type not in ['audio', 'video']:
        flash('Invalid call type.', 'error')
        return redirect(url_for('dm_conversation', user_id=user_id))
    
    # Check for existing active call
    existing_call = Call.query.filter(
        ((Call.caller_id == current_user.id) | (Call.recipient_id == current_user.id)),
        Call.status.in_(['pending', 'active'])
    ).first()
    
    if existing_call:
        flash('You already have an active call.', 'error')
        return redirect(url_for('dm_conversation', user_id=user_id))
    
    call = Call(
        caller_id=current_user.id,
        recipient_id=user_id,
        call_type=call_type,
        status='pending'
    )
    db.session.add(call)
    db.session.commit()
    
    # Send call notification to recipient via SocketIO
    from app import socketio
    socketio.emit('incoming_call', {
        'call_id': call.id,
        'caller_id': current_user.id,
        'caller_name': current_user.first_name or current_user.username,
        'caller_avatar': current_user.profile_image_url,
        'call_type': call_type
    }, to=f'user_{user_id}')
    
    return render_template('call.html', 
                         call=call, 
                         other_user=other_user, 
                         is_caller=True)

@app.route('/join_call/<int:call_id>')
@require_login
def join_call(call_id):
    call = Call.query.get_or_404(call_id)
    
    if call.recipient_id != current_user.id:
        flash('You are not authorized to join this call.', 'error')
        return redirect(url_for('home'))
    
    if call.status != 'pending':
        flash('This call is no longer available.', 'error')
        return redirect(url_for('home'))
    
    call.status = 'active'
    db.session.commit()
    
    other_user = User.query.get(call.caller_id)
    return render_template('call.html', 
                         call=call, 
                         other_user=other_user, 
                         is_caller=False)

@app.route('/end_call/<int:call_id>', methods=['POST'])
@require_login
def end_call(call_id):
    call = Call.query.get_or_404(call_id)
    
    if call.caller_id != current_user.id and call.recipient_id != current_user.id:
        flash('You are not authorized to end this call.', 'error')
        return redirect(url_for('home'))
    
    call.status = 'ended'
    call.ended_at = datetime.now()
    db.session.commit()
    
    return jsonify({'status': 'success'})

# API endpoints for call management
@app.route('/api/calls/<int:call_id>/accept', methods=['POST'])
@require_login
def api_accept_call(call_id):
    call = Call.query.get_or_404(call_id)
    
    if call.recipient_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if call.status != 'pending':
        return jsonify({'error': 'Call is no longer available'}), 400
    
    call.status = 'active'
    db.session.commit()
    
    # Emit call accepted event via SocketIO
    from app import socketio
    socketio.emit('call_accepted', {
        'call_id': call_id,
        'recipient_id': current_user.id
    }, to=f'call_{call_id}')
    
    return jsonify({'status': 'success'}), 200

@app.route('/api/calls/<int:call_id>/decline', methods=['POST'])
@require_login
def api_decline_call(call_id):
    call = Call.query.get_or_404(call_id)
    
    if call.recipient_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if call.status != 'pending':
        return jsonify({'error': 'Call is no longer available'}), 400
    
    call.status = 'declined'
    call.ended_at = datetime.now()
    db.session.commit()
    
    # Emit call declined event via SocketIO
    from app import socketio
    socketio.emit('call_declined', {
        'call_id': call_id,
        'recipient_id': current_user.id
    }, to=f'call_{call_id}')
    
    return jsonify({'status': 'success'}), 200

@app.route('/api/calls/<int:call_id>/end', methods=['POST'])
@require_login
def api_end_call(call_id):
    call = Call.query.get_or_404(call_id)
    
    if call.caller_id != current_user.id and call.recipient_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    call.status = 'ended'
    call.ended_at = datetime.now()
    db.session.commit()
    
    # Emit call ended event via SocketIO
    from app import socketio
    socketio.emit('call_ended', {
        'call_id': call_id,
        'ended_by': current_user.id
    }, to=f'call_{call_id}')
    
    return jsonify({'status': 'success'}), 200

@app.route('/profile')
@require_login
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/edit_profile', methods=['GET', 'POST'])
@require_login
def edit_profile():
    if request.method == 'POST':
        current_user.username = request.form.get('username') or current_user.username
        current_user.bio = request.form.get('bio')
        current_user.location = request.form.get('location')
        current_user.status = request.form.get('status') or 'online'
        
        # Handle resized image data first (takes priority)
        resized_image_data = request.form.get('resized_image_data')
        if resized_image_data and resized_image_data.startswith('data:image/'):
            try:
                # Validate data URL format
                if 'base64,' in resized_image_data:
                    current_user.profile_image_url = resized_image_data
                    flash('Profile photo updated successfully!', 'success')
                else:
                    flash('Invalid image data format.', 'error')
                    return render_template('edit_profile.html', user=current_user)
            except Exception as e:
                flash('Error processing resized image. Please try again.', 'error')
                return render_template('edit_profile.html', user=current_user)
        else:
            # Handle file upload
            profile_image = request.files.get('profile_image')
            if profile_image and profile_image.filename:
                # Validate file type
                allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                file_ext = os.path.splitext(profile_image.filename)[1].lower()
                
                if file_ext in allowed_extensions:
                    try:
                        # Read file and convert to base64 data URL
                        file_data = profile_image.read()
                        
                        # Check file size (limit to 5MB)
                        if len(file_data) > 5 * 1024 * 1024:
                            flash('Image file too large. Please use an image under 5MB.', 'error')
                            return render_template('edit_profile.html', user=current_user)
                        
                        # Create data URL
                        mime_type = f"image/{file_ext[1:]}" if file_ext != '.jpg' else "image/jpeg"
                        base64_data = base64.b64encode(file_data).decode('utf-8')
                        data_url = f"data:{mime_type};base64,{base64_data}"
                        
                        current_user.profile_image_url = data_url
                        flash('Profile photo uploaded successfully!', 'success')
                        
                    except Exception as e:
                        flash('Error processing image file. Please try again.', 'error')
                        return render_template('edit_profile.html', user=current_user)
                else:
                    flash('Invalid file type. Please use JPG, PNG, GIF, or WebP images.', 'error')
                    return render_template('edit_profile.html', user=current_user)
            else:
                # Handle custom profile image URL if no file uploaded
                profile_image_url = request.form.get('profile_image_url')
                if profile_image_url:
                    current_user.profile_image_url = profile_image_url
            
        current_user.updated_at = datetime.now()
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('edit_profile.html', user=current_user)

@app.route('/voicemails')
@require_login
def voicemails():
    received_voicemails = Voicemail.query.filter_by(recipient_id=current_user.id).order_by(Voicemail.created_at.desc()).all()
    sent_voicemails = Voicemail.query.filter_by(sender_id=current_user.id).order_by(Voicemail.created_at.desc()).all()
    return render_template('voicemails.html', received=received_voicemails, sent=sent_voicemails)

@app.route('/send_voicemail/<user_id>', methods=['POST'])
@require_login
def send_voicemail(user_id):
    audio_url = request.form.get('audio_url')
    duration = request.form.get('duration', type=int)
    
    if not audio_url:
        flash('Audio recording required', 'error')
        return redirect(url_for('dm_conversation', user_id=user_id))
    
    voicemail = Voicemail(
        sender_id=current_user.id,
        recipient_id=user_id,
        audio_url=audio_url,
        duration=duration
    )
    db.session.add(voicemail)
    db.session.commit()
    
    flash('Voicemail sent!', 'success')
    return redirect(url_for('dm_conversation', user_id=user_id))

@app.route('/mark_voicemail_read/<int:voicemail_id>', methods=['POST'])
@require_login
def mark_voicemail_read(voicemail_id):
    voicemail = Voicemail.query.get_or_404(voicemail_id)
    if voicemail.recipient_id != current_user.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('voicemails'))
    
    voicemail.is_read = True
    db.session.commit()
    return jsonify({'status': 'success'})

def auto_add_user_to_servers(user):
    """Automatically add new users to all public servers"""
    try:
        public_servers = Server.query.filter_by(is_public=True).all()
        for server in public_servers:
            existing_membership = ServerMembership.query.filter_by(
                user_id=user.id, 
                server_id=server.id
            ).first()
            
            if not existing_membership:
                membership = ServerMembership(user_id=user.id, server_id=server.id)
                db.session.add(membership)
        
        # Don't commit here - let the calling function handle the commit
        logging.info(f"Added user {user.id} to {len(public_servers)} public servers")
        
    except Exception as e:
        logging.error(f"Error auto-adding user to servers: {e}")
        # Don't raise the exception, just log it

@app.route('/server_call/<int:server_id>')
@require_login
def server_call(server_id):
    server = Server.query.get_or_404(server_id)
    
    # Check if user is member of server
    membership = ServerMembership.query.filter_by(
        user_id=current_user.id,
        server_id=server_id
    ).first()
    
    if not membership:
        flash('You are not a member of this server', 'error')
        return redirect(url_for('home'))
    
    # Get active server calls
    active_calls = Call.query.filter_by(
        server_id=server_id,
        status='active'
    ).all()
    
    return render_template('server_call.html', server=server, active_calls=active_calls)

@app.route('/initiate_server_call/<int:server_id>', methods=['POST'])
@require_login
def initiate_server_call(server_id):
    call_type = request.form.get('call_type', 'audio')
    
    # Create server call
    call = Call(
        caller_id=current_user.id,
        recipient_id=current_user.id,  # For server calls, we'll use same ID
        server_id=server_id,
        call_type=call_type,
        status='active'
    )
    db.session.add(call)
    db.session.commit()
    
    return redirect(url_for('server_call', server_id=server_id))

@app.route('/send_call_message/<int:call_id>', methods=['POST'])
@require_login
def send_call_message(call_id):
    content = request.form.get('content')
    if not content:
        return jsonify({'error': 'Message content required'}), 400
    
    call = Call.query.get_or_404(call_id)
    
    message = CallMessage(
        call_id=call_id,
        user_id=current_user.id,
        content=content
    )
    db.session.add(message)
    db.session.commit()
    
    return jsonify({
        'id': message.id,
        'content': message.content,
        'user': current_user.username or current_user.first_name or 'Anonymous',
        'timestamp': message.created_at.strftime('%H:%M')
    })

@app.route('/update_server_logo/<int:server_id>', methods=['POST'])
@require_login
def update_server_logo(server_id):
    server = Server.query.get_or_404(server_id)
    
    if server.owner_id != current_user.id:
        flash('Only the server owner can update the logo.', 'error')
        return redirect(url_for('server_view', server_id=server_id))
    
    logo_file = request.files.get('logo_file')
    if logo_file and logo_file.filename:
        # Validate file type
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        file_ext = os.path.splitext(logo_file.filename)[1].lower()
        
        if file_ext in allowed_extensions:
            try:
                # Read file and convert to base64 data URL
                file_data = logo_file.read()
                
                # Check file size (limit to 2MB)
                if len(file_data) > 2 * 1024 * 1024:
                    flash('Logo file too large. Please use an image under 2MB.', 'error')
                    return redirect(url_for('server_view', server_id=server_id))
                
                # Create data URL
                mime_type = f"image/{file_ext[1:]}" if file_ext != '.jpg' else "image/jpeg"
                base64_data = base64.b64encode(file_data).decode('utf-8')
                data_url = f"data:{mime_type};base64,{base64_data}"
                
                server.logo_url = data_url
                db.session.commit()
                flash('Server logo updated successfully!', 'success')
                
            except Exception as e:
                flash('Error processing logo file. Please try again.', 'error')
        else:
            flash('Invalid file type. Please use JPG, PNG, GIF, or WebP images.', 'error')
    
    return redirect(url_for('server_view', server_id=server_id))

@app.route('/servers/<int:server_id>/edit', methods=['POST'])
@require_login
def edit_server(server_id):
    """Edit server information"""
    server = Server.query.get_or_404(server_id)
    
    # Only server owner can edit
    if server.owner_id != current_user.id:
        abort(403)
    
    name = sanitize_input(request.form.get('name', '').strip(), 100)
    description = sanitize_input(request.form.get('description', '').strip(), 500)
    is_public = request.form.get('is_public') == '1'
    
    if not name:
        flash('Server name is required', 'error')
        return redirect(url_for('server_view', server_id=server_id))
    
    # Check if name is already taken by another server
    existing_server = Server.query.filter(Server.name == name, Server.id != server_id).first()
    if existing_server:
        flash('A server with this name already exists', 'error')
        return redirect(url_for('server_view', server_id=server_id))
    
    server.name = name
    server.description = description if description else None
    server.is_public = is_public
    
    db.session.commit()
    
    # If changed to public, auto-add all users
    if is_public:
        try:
            all_users = User.query.all()
            for user in all_users:
                existing_membership = ServerMembership.query.filter_by(
                    user_id=user.id, 
                    server_id=server_id
                ).first()
                
                if not existing_membership:
                    membership = ServerMembership(user_id=user.id, server_id=server_id)
                    db.session.add(membership)
            
            db.session.commit()
            logging.info(f"Auto-added all users to public server {server_id}")
        except Exception as e:
            logging.error(f"Error auto-adding users to public server: {e}")
            db.session.rollback()
    
    flash('Server information updated successfully', 'success')
    return redirect(url_for('server_view', server_id=server_id))

@app.route('/servers/<int:server_id>/delete', methods=['POST'])
@require_login
def delete_server(server_id):
    """Delete server and all associated data"""
    server = Server.query.get_or_404(server_id)
    
    # Only server owner can delete
    if server.owner_id != current_user.id:
        abort(403)
    
    confirm_name = request.form.get('confirm_name', '').strip()
    if confirm_name != server.name:
        flash('Server name confirmation does not match', 'error')
        return redirect(url_for('server_view', server_id=server_id))
    
    # Delete server (cascade will handle channels, messages, memberships, etc.)
    db.session.delete(server)
    db.session.commit()
    
    flash(f'Server "{server.name}" has been permanently deleted', 'success')
    return redirect(url_for('home'))

@app.route('/upload_file/<int:server_id>', methods=['POST'])
@require_login
def upload_file(server_id):
    server = Server.query.get_or_404(server_id)
    
    # Check if user is member of server
    is_member = ServerMembership.query.filter_by(
        user_id=current_user.id, 
        server_id=server_id
    ).first() is not None
    
    is_owner = server.owner_id == current_user.id
    
    if not (is_member or is_owner):
        flash('You do not have access to this server.', 'error')
        return redirect(url_for('home'))
    
    uploaded_file = request.files.get('file')
    if uploaded_file and uploaded_file.filename:
        try:
            # Read file data
            file_data = uploaded_file.read()
            
            # Check file size (limit to 10MB)
            if len(file_data) > 10 * 1024 * 1024:
                flash('File too large. Please use a file under 10MB.', 'error')
                return redirect(url_for('server_view', server_id=server_id))
            
            # Get or create general channel
            channel = server.channels[0] if server.channels else None
            if not channel:
                channel = Channel(name='general', server_id=server_id)
                db.session.add(channel)
                db.session.flush()
            
            # Create file record
            shared_file = SharedFile(
                filename=str(uuid.uuid4()) + '_' + uploaded_file.filename,
                original_filename=uploaded_file.filename,
                file_data=file_data,
                file_size=len(file_data),
                mime_type=uploaded_file.content_type or 'application/octet-stream',
                uploader_id=current_user.id,
                server_id=server_id,
                channel_id=channel.id
            )
            db.session.add(shared_file)
            
            # Create message about file upload
            message = Message(
                content=f"📎 {current_user.username or current_user.first_name or 'User'} uploaded: {uploaded_file.filename}",
                author_id=current_user.id,
                channel_id=channel.id
            )
            db.session.add(message)
            db.session.commit()
            
            flash(f'File "{uploaded_file.filename}" uploaded successfully!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash('Error uploading file. Please try again.', 'error')
    
    return redirect(url_for('server_view', server_id=server_id))

@app.route('/download_file/<int:file_id>')
@require_login
def download_file(file_id):
    shared_file = SharedFile.query.get_or_404(file_id)
    
    # Check if user has access to the file
    if shared_file.server_id:
        is_member = ServerMembership.query.filter_by(
            user_id=current_user.id, 
            server_id=shared_file.server_id
        ).first() is not None
        
        is_owner = shared_file.server.owner_id == current_user.id
        
        if not (is_member or is_owner):
            flash('You do not have access to this file.', 'error')
            return redirect(url_for('home'))
    
    from flask import Response
    return Response(
        shared_file.file_data,
        mimetype=shared_file.mime_type,
        headers={
            'Content-Disposition': f'attachment; filename="{shared_file.original_filename}"'
        }
    )

@app.route('/create_invitation', methods=['POST'])
@require_login
def create_invitation():
    import secrets
    
    code = secrets.token_urlsafe(16)
    email = request.form.get('email', '').strip()
    
    invitation = Invitation(
        code=code,
        inviter_id=current_user.id,
        email=email if email else None,
        uses_left=5  # Allow 5 uses per invitation
    )
    db.session.add(invitation)
    db.session.commit()
    
    base_url = request.url_root.rstrip('/')
    invite_url = f"{base_url}/invite/{code}"
    
    # Send email if email address is provided
    if email:
        try:
            send_invitation_email(email, invite_url, current_user.username or current_user.first_name or 'A friend')
            flash(f'Invitation sent to {email}!', 'success')
        except Exception as e:
            flash('Invitation created but email could not be sent. You can still share the link manually.', 'warning')
    
    return jsonify({
        'success': True,
        'invite_url': invite_url,
        'code': code,
        'email_sent': bool(email)
    })

def send_invitation_email(to_email, invite_url, inviter_name):
    """Send invitation email using a simple email service"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    # For demo purposes, we'll just log the email content
    # In production, you'd configure SMTP settings
    subject = f"{inviter_name} invited you to join CommunicationX!"
    
    body = f"""
    Hi there!
    
    {inviter_name} has invited you to join CommunicationX, a modern communication platform.
    
    Click the link below to join:
    {invite_url}
    
    This invitation can be used up to 5 times and doesn't expire.
    
    Welcome to CommunicationX!
    """
    
    # Log the email content (replace with actual SMTP in production)
    print(f"EMAIL TO: {to_email}")
    print(f"SUBJECT: {subject}")
    print(f"BODY: {body}")
    
    # For production, uncomment and configure:
    # msg = MIMEMultipart()
    # msg['From'] = "noreply@communicationx.com"
    # msg['To'] = to_email
    # msg['Subject'] = subject
    # msg.attach(MIMEText(body, 'plain'))
    # 
    # server = smtplib.SMTP('your-smtp-server.com', 587)
    # server.starttls()
    # server.login("your-email@domain.com", "your-password")
    # server.send_message(msg)
    # server.quit()

@app.route('/invite/<code>')
def join_by_invitation(code):
    invitation = Invitation.query.filter_by(code=code).first()
    
    if not invitation or invitation.uses_left <= 0:
        flash('Invalid or expired invitation.', 'error')
        return redirect(url_for('index'))
    
    if current_user.is_authenticated:
        flash('Welcome to CommunicationX! You can now join servers and start chatting.', 'success')
        return redirect(url_for('home'))
    
    # Store invitation code in session for after signup
    session['invitation_code'] = code
    flash('Please sign up to join CommunicationX!', 'info')
    return redirect(url_for('custom_signup'))

@app.route('/start_call/<call_type>/<user_id>')
@require_login
def start_call(call_type, user_id):
    other_user = User.query.get_or_404(user_id)
    
    if call_type not in ['audio', 'video']:
        flash('Invalid call type.', 'error')
        return redirect(url_for('dm_conversation', user_id=user_id))
    
    # Check for existing active call
    existing_call = Call.query.filter(
        ((Call.caller_id == current_user.id) | (Call.recipient_id == current_user.id)),
        Call.status.in_(['pending', 'active'])
    ).first()
    
    if existing_call:
        flash('You already have an active call.', 'error')
        return redirect(url_for('dm_conversation', user_id=user_id))
    
    call = Call(
        caller_id=current_user.id,
        recipient_id=user_id,
        call_type=call_type,
        status='active'
    )
    db.session.add(call)
    db.session.commit()
    
    return render_template('call_screen.html', 
                         call=call, 
                         other_user=other_user, 
                         is_caller=True)

@app.route('/start_server_call/<int:server_id>/<call_type>')
@require_login
def start_server_call(server_id, call_type):
    server = Server.query.get_or_404(server_id)
    
    # Check if user is member of server
    membership = ServerMembership.query.filter_by(
        user_id=current_user.id,
        server_id=server_id
    ).first()
    
    if not membership and server.owner_id != current_user.id:
        flash('You are not a member of this server', 'error')
        return redirect(url_for('home'))
    
    if call_type not in ['audio', 'video']:
        flash('Invalid call type.', 'error')
        return redirect(url_for('server_view', server_id=server_id))
    
    # Create server call
    call = Call(
        caller_id=current_user.id,
        recipient_id=current_user.id,  # For server calls
        server_id=server_id,
        call_type=call_type,
        status='active'
    )
    db.session.add(call)
    db.session.commit()
    
    return render_template('call_screen.html', 
                         call=call, 
                         server=server, 
                         is_server_call=True)

# Message Management Routes
@app.route('/message/<int:message_id>/delete', methods=['POST'])
@require_login
def delete_message(message_id):
    message = Message.query.get_or_404(message_id)
    
    # Check permissions
    if message.author_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        db.session.delete(message)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete message'}), 500

@app.route('/message/<int:message_id>/react', methods=['POST'])
@require_login
def react_to_message(message_id):
    message = Message.query.get_or_404(message_id)
    emoji = request.json.get('emoji')
    
    if not emoji:
        return jsonify({'error': 'Emoji required'}), 400
    
    try:
        # Check if reaction already exists
        existing_reaction = MessageReaction.query.filter_by(
            message_id=message_id,
            user_id=current_user.id,
            emoji=emoji
        ).first()
        
        if existing_reaction:
            # Remove reaction if it exists
            db.session.delete(existing_reaction)
            action = 'removed'
        else:
            # Add new reaction
            reaction = MessageReaction(
                message_id=message_id,
                user_id=current_user.id,
                emoji=emoji
            )
            db.session.add(reaction)
            action = 'added'
        
        db.session.commit()
        return jsonify({'success': True, 'action': action})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to process reaction'}), 500

@app.route('/message/<int:message_id>/pin', methods=['POST'])
@require_login
def pin_message(message_id):
    message = Message.query.get_or_404(message_id)
    
    # Check if user has permission (author or server owner)
    channel = Channel.query.get(message.channel_id)
    server = Server.query.get(channel.server_id)
    
    if message.author_id != current_user.id and server.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        message.is_pinned = not message.is_pinned
        db.session.commit()
        return jsonify({'success': True, 'pinned': message.is_pinned})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update pin status'}), 500

@app.route('/message/<int:message_id>/report', methods=['POST'])
@require_login
def report_message(message_id):
    message = Message.query.get_or_404(message_id)
    reason = request.json.get('reason')
    description = request.json.get('description', '')
    
    if not reason:
        return jsonify({'error': 'Report reason required'}), 400
    
    try:
        report = MessageReport(
            message_id=message_id,
            reporter_id=current_user.id,
            reason=reason,
            description=description
        )
        db.session.add(report)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to submit report'}), 500

@app.route('/message/<int:message_id>/reply', methods=['POST'])
@require_login
def reply_to_message(message_id):
    original_message = Message.query.get_or_404(message_id)
    content = sanitize_input(request.json.get('content', ''), max_length=2000)
    
    if not content or len(content.strip()) == 0:
        return jsonify({'error': 'Message content required'}), 400
    
    try:
        reply = Message(
            content=content,
            author_id=current_user.id,
            channel_id=original_message.channel_id,
            reply_to_id=message_id
        )
        db.session.add(reply)
        db.session.commit()
        return jsonify({'success': True, 'message_id': reply.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to send reply'}), 500

@app.route('/message/<int:message_id>/forward', methods=['POST'])
@require_login
def forward_message(message_id):
    original_message = Message.query.get_or_404(message_id)
    recipient_id = request.json.get('recipient_id')
    
    if not recipient_id:
        return jsonify({'error': 'Recipient required'}), 400
    
    try:
        # Create direct message with forwarded content
        forwarded_content = f"Forwarded message: {original_message.content}"
        
        dm = DirectMessage(
            content=forwarded_content,
            sender_id=current_user.id,
            recipient_id=recipient_id
        )
        db.session.add(dm)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to forward message'}), 500

@app.route('/message/<int:message_id>/audio', methods=['POST'])
@require_login
def send_audio_message(message_id=None):
    audio_file = request.files.get('audio')
    channel_id = request.form.get('channel_id')
    
    if not audio_file or not channel_id:
        return jsonify({'error': 'Audio file and channel required'}), 400
    
    try:
        # Store audio data
        audio_data = audio_file.read()
        
        message = Message(
            content="Audio message",
            author_id=current_user.id,
            channel_id=int(channel_id),
            message_type='audio',
            file_data=audio_data
        )
        db.session.add(message)
        db.session.commit()
        return jsonify({'success': True, 'message_id': message.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to send audio message'}), 500

# Tools Routes
@app.route('/tools/hackkit/<workspace_type>')
@require_login
def hackkit(workspace_type):
    """HackKit code editor interface"""
    if workspace_type not in ['personal', 'group']:
        return redirect(url_for('home'))
    return render_template('tools/hackkit.html', workspace_type=workspace_type, workspaces=[])

@app.route('/tools/canva/<workspace_type>')
@require_login
def canva(workspace_type):
    """Canva design tool interface"""
    if workspace_type not in ['personal', 'group']:
        return redirect(url_for('home'))
    return render_template('tools/canva.html', workspace_type=workspace_type, workspaces=[])

@app.route('/tools/opera/<session_type>')
@require_login
def opera(session_type):
    """Opera browser interface"""
    if session_type not in ['personal', 'group']:
        return redirect(url_for('home'))
    return render_template('tools/opera.html', session_type=session_type, sessions=[])

@app.route('/tools/files')
@require_login
def files_manager():
    """Files manager interface"""
    return render_template('tools/files.html', code_files=[], design_files=[], browser_files=[])
