from datetime import datetime
from app import db
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint, Index, text

# (IMPORTANT) This table is mandatory for Replit Auth, don't drop it.
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String, unique=True, nullable=True)
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    profile_image_url = db.Column(db.String, nullable=True)
    username = db.Column(db.String(64), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='online')  # online, away, busy, invisible
    location = db.Column(db.String(100), nullable=True)
    custom_status = db.Column(db.String(128), nullable=True)  # Custom status message
    banner_url = db.Column(db.String, nullable=True)  # Profile banner
    accent_color = db.Column(db.String(7), nullable=True)  # Hex color for profile
    is_bot = db.Column(db.Boolean, default=False)  # Bot accounts
    bot_token = db.Column(db.String, nullable=True)  # Bot authentication token
    two_factor_enabled = db.Column(db.Boolean, default=False)  # 2FA security
    phone_number = db.Column(db.String(20), nullable=True)  # For notifications
    email_verified = db.Column(db.Boolean, default=False)  # Email verification
    last_seen = db.Column(db.DateTime, default=datetime.now)  # Last activity
    
    # Admin privileges
    is_admin = db.Column(db.Boolean, default=False)  # App administrator
    is_super_admin = db.Column(db.Boolean, default=False)  # Super administrator
    admin_permissions = db.Column(db.Text, nullable=True)  # JSON permissions
    is_banned = db.Column(db.Boolean, default=False)  # Banned status
    ban_reason = db.Column(db.Text, nullable=True)  # Reason for ban
    banned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Who banned
    banned_at = db.Column(db.DateTime, nullable=True)  # When banned
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    owned_servers = db.relationship('Server', foreign_keys='Server.owner_id', backref='owner', lazy=True)
    messages = db.relationship('Message', backref='author', lazy=True)
    direct_messages_sent = db.relationship('DirectMessage', foreign_keys='DirectMessage.sender_id', backref='sender', lazy=True)
    direct_messages_received = db.relationship('DirectMessage', foreign_keys='DirectMessage.recipient_id', backref='recipient', lazy=True)

# (IMPORTANT) This table is mandatory for Replit Auth, don't drop it.
class OAuth(OAuthConsumerMixin, db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    browser_session_key = db.Column(db.String, nullable=False)
    user = db.relationship(User)

    __table_args__ = (UniqueConstraint(
        'user_id',
        'browser_session_key',
        'provider',
        name='uq_user_browser_session_key_provider',
    ),)

class Server(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    logo_url = db.Column(db.String, nullable=True)
    banner_url = db.Column(db.String, nullable=True)  # Server banner
    owner_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    is_public = db.Column(db.Boolean, default=True)  # Public servers auto-add all users
    verification_level = db.Column(db.Integer, default=0)  # 0=None, 1=Low, 2=Medium, 3=High, 4=Highest
    explicit_content_filter = db.Column(db.Integer, default=0)  # Content filtering
    default_notifications = db.Column(db.String(20), default='all')  # all, mentions
    vanity_url = db.Column(db.String(50), unique=True, nullable=True)  # Custom invite URL
    boost_level = db.Column(db.Integer, default=0)  # Server boost level
    boost_count = db.Column(db.Integer, default=0)  # Number of boosts
    max_members = db.Column(db.Integer, default=500000)  # Member limit
    max_presences = db.Column(db.Integer, default=25000)  # Presence limit
    max_video_channel_users = db.Column(db.Integer, default=25)  # Video channel limit
    afk_timeout = db.Column(db.Integer, default=300)  # AFK timeout in seconds
    afk_channel_id = db.Column(db.Integer, nullable=True)  # AFK voice channel
    system_channel_id = db.Column(db.Integer, nullable=True)  # System messages channel
    rules_channel_id = db.Column(db.Integer, nullable=True)  # Rules channel
    public_updates_channel_id = db.Column(db.Integer, nullable=True)  # Public updates channel
    preferred_locale = db.Column(db.String(10), default='en-US')  # Server language
    features = db.Column(db.Text, nullable=True)  # JSON array of server features
    
    # Server security features
    password_hash = db.Column(db.String(256), nullable=True)  # Server password protection
    password_enabled = db.Column(db.Boolean, default=False)  # Whether password is required
    password_set_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Admin who set password
    password_set_at = db.Column(db.DateTime, nullable=True)  # When password was set
    is_locked = db.Column(db.Boolean, default=False)  # Server locked by admin
    locked_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Admin who locked
    locked_at = db.Column(db.DateTime, nullable=True)  # When server was locked
    lock_reason = db.Column(db.Text, nullable=True)  # Reason for locking
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    channels = db.relationship('Channel', backref='server', lazy=True, cascade='all, delete-orphan')
    memberships = db.relationship('ServerMembership', backref='server', lazy=True, cascade='all, delete-orphan')
    roles = db.relationship('Role', backref='server', lazy=True, cascade='all, delete-orphan')
    emojis = db.relationship('CustomEmoji', backref='server', lazy=True, cascade='all, delete-orphan')
    stickers = db.relationship('Sticker', backref='server', lazy=True, cascade='all, delete-orphan')
    bans = db.relationship('ServerBan', backref='server', lazy=True, cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='server', lazy=True, cascade='all, delete-orphan')

class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    channel_type = db.Column(db.String(20), default='text')  # text, voice, category, announcement, stage, forum, thread
    topic = db.Column(db.String(1024), nullable=True)  # Channel description
    position = db.Column(db.Integer, default=0)  # Channel sort order
    parent_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=True)  # Category parent
    bitrate = db.Column(db.Integer, nullable=True)  # Voice channel bitrate
    user_limit = db.Column(db.Integer, nullable=True)  # Voice channel user limit
    rate_limit_per_user = db.Column(db.Integer, default=0)  # Slowmode seconds
    nsfw = db.Column(db.Boolean, default=False)  # Age-restricted content
    rtc_region = db.Column(db.String(20), nullable=True)  # Voice region
    video_quality_mode = db.Column(db.Integer, default=1)  # 1=auto, 2=720p
    default_auto_archive_duration = db.Column(db.Integer, default=4320)  # Thread auto-archive (minutes)
    permissions_overwrites = db.Column(db.Text, nullable=True)  # JSON permission overwrites
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    messages = db.relationship('Message', backref='channel', lazy=True, cascade='all, delete-orphan')
    threads = db.relationship('Thread', backref='parent_channel', lazy=True, cascade='all, delete-orphan')
    webhooks = db.relationship('Webhook', backref='channel', lazy=True, cascade='all, delete-orphan')
    
    # Self-referential relationship for categories
    children = db.relationship('Channel', backref=db.backref('parent', remote_side=[id]))

class ServerMembership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    nickname = db.Column(db.String(32), nullable=True)  # Server-specific nickname
    avatar_url = db.Column(db.String, nullable=True)  # Server-specific avatar
    roles = db.Column(db.Text, nullable=True)  # JSON array of role IDs
    joined_at = db.Column(db.DateTime, default=datetime.now)
    premium_since = db.Column(db.DateTime, nullable=True)  # Server boost date
    deaf = db.Column(db.Boolean, default=False)  # Server deafened
    mute = db.Column(db.Boolean, default=False)  # Server muted
    pending = db.Column(db.Boolean, default=False)  # Pending verification
    communication_disabled_until = db.Column(db.DateTime, nullable=True)  # Timeout
    
    # Relationships
    user = db.relationship('User', backref='server_memberships')

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.BigInteger, primary_key=True)  # BigInt for large-scale storage
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False, index=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True, nullable=False)
    edited_at = db.Column(db.DateTime, nullable=True)
    is_pinned = db.Column(db.Boolean, default=False, index=True)  # Index for pinned message queries
    reply_to_id = db.Column(db.BigInteger, nullable=True, index=True)  # Remove FK constraint for partitioning
    message_type = db.Column(db.String(20), default='text', index=True)  # Index for message type filtering
    audio_url = db.Column(db.String, nullable=True)  # For audio messages
    file_data = db.Column(db.LargeBinary, nullable=True)  # For file attachments
    
    # Message status indicators
    status = db.Column(db.String(20), default='sending', index=True)  # sending, sent, delivered, read, failed
    delivered_at = db.Column(db.DateTime, nullable=True)  # When message was delivered
    read_at = db.Column(db.DateTime, nullable=True)  # When message was read
    read_by = db.relationship('MessageReadStatus', backref='message', cascade='all, delete-orphan')
    
    # Relationships (without FK constraint for reply_to due to partitioning)
    reactions = db.relationship('MessageReaction', backref='message', cascade='all, delete-orphan')
    reports = db.relationship('MessageReport', backref='message', cascade='all, delete-orphan')
    
    # Composite indexes for efficient queries
    __table_args__ = (
        Index('idx_channel_created_at', 'channel_id', 'created_at'),  # For chronological message retrieval
        Index('idx_author_created_at', 'author_id', 'created_at'),    # For user message history
        Index('idx_channel_type_created', 'channel_id', 'message_type', 'created_at'),  # For filtered message queries
        Index('idx_pinned_channel', 'is_pinned', 'channel_id'),       # For pinned messages
        Index('idx_reply_lookup', 'reply_to_id', 'created_at'),       # For reply lookups
    )

class DirectMessage(db.Model):
    __tablename__ = 'direct_messages'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)  # BigInt for large-scale storage
    content = db.Column(db.Text, nullable=False)
    sender_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False, index=True)
    recipient_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # Message status indicators for DMs
    status = db.Column(db.String(20), default='sending', index=True)  # sending, sent, delivered, read, failed
    delivered_at = db.Column(db.DateTime, nullable=True)  # When message was delivered
    
    # Composite indexes for efficient DM queries
    __table_args__ = (
        Index('idx_dm_conversation', 'sender_id', 'recipient_id', 'created_at'),  # For conversation threads
        Index('idx_dm_recipient_unread', 'recipient_id', 'read_at', 'created_at'),  # For unread messages
        Index('idx_dm_user_timeline', 'sender_id', 'created_at'),  # For user message timeline
    )

class MessageReadStatus(db.Model):
    """Track read status for messages in group channels"""
    __tablename__ = 'message_read_status'
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.BigInteger, db.ForeignKey('messages.id'), nullable=False, index=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False, index=True)
    read_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    
    # Composite index for efficient read status queries
    __table_args__ = (
        Index('idx_message_user_read', 'message_id', 'user_id'),
        UniqueConstraint('message_id', 'user_id', name='uq_message_user_read'),
    )

class Call(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    caller_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=True)  # For server calls
    call_type = db.Column(db.String(10), nullable=False)  # 'audio' or 'video'
    status = db.Column(db.String(20), default='pending')  # 'pending', 'active', 'ended', 'declined'
    started_at = db.Column(db.DateTime, default=datetime.now)
    ended_at = db.Column(db.DateTime, nullable=True)
    voicemail_url = db.Column(db.String, nullable=True)  # For voicemail recordings
    
    # Relationships
    caller = db.relationship('User', foreign_keys=[caller_id], backref='calls_made')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='calls_received')
    server = db.relationship('Server', backref='server_calls')

class CallMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    call_id = db.Column(db.Integer, db.ForeignKey('call.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    call = db.relationship('Call', backref='call_messages')
    user = db.relationship('User', backref='call_messages')

class SharedFile(db.Model):
    __tablename__ = 'shared_files'
    
    id = db.Column(db.BigInteger, primary_key=True)  # BigInt for large-scale storage
    filename = db.Column(db.String(255), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    file_data = db.Column(db.LargeBinary, nullable=True)  # Store large files externally for 1TB+ support
    file_path = db.Column(db.String(500), nullable=True)  # External file storage path
    file_size = db.Column(db.BigInteger, nullable=False, index=True)  # BigInt for large files
    mime_type = db.Column(db.String(100), nullable=False, index=True)
    uploader_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False, index=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=True, index=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    is_compressed = db.Column(db.Boolean, default=False)  # Track compression status
    checksum = db.Column(db.String(64), nullable=True)  # File integrity verification
    
    # Relationships
    uploader = db.relationship('User', backref='uploaded_files')
    server = db.relationship('Server', backref='shared_files')
    channel = db.relationship('Channel', backref='shared_files')
    
    # Indexes for efficient file queries
    __table_args__ = (
        Index('idx_file_type_size', 'mime_type', 'file_size'),  # For file type and size filtering
        Index('idx_server_files', 'server_id', 'created_at'),  # For server file listings
        Index('idx_channel_files', 'channel_id', 'created_at'),  # For channel file listings
        Index('idx_user_uploads', 'uploader_id', 'created_at'),  # For user upload history
    )

class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)
    inviter_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    uses_left = db.Column(db.Integer, default=1)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    inviter = db.relationship('User', backref='invitations_sent')

class Voicemail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    audio_url = db.Column(db.String, nullable=False)
    duration = db.Column(db.Integer, nullable=True)  # in seconds
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], backref='voicemails_sent')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='voicemails_received')

# HackKit - Code Editor and Development Environment
class CodeWorkspace(db.Model):
    __tablename__ = 'code_workspaces'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    workspace_type = db.Column(db.String(20), nullable=False)  # 'personal' or 'group'
    owner_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=True)  # For group workspaces
    language = db.Column(db.String(50), default='javascript')  # python, javascript, java, cpp, etc.
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    owner = db.relationship('User', backref='owned_workspaces')
    server = db.relationship('Server', backref='code_workspaces')

class CodeFile(db.Model):
    __tablename__ = 'code_files'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('code_workspaces.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)  # Full path in workspace
    content = db.Column(db.Text, nullable=True)
    language = db.Column(db.String(50), nullable=True)
    size = db.Column(db.Integer, default=0)
    created_by = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    workspace = db.relationship('CodeWorkspace', backref='files')
    creator = db.relationship('User', backref='created_files')

class WorkspaceCollaborator(db.Model):
    __tablename__ = 'workspace_collaborators'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('code_workspaces.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    permission = db.Column(db.String(20), default='read')  # read, write, admin
    joined_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    workspace = db.relationship('CodeWorkspace', backref='collaborators')
    user = db.relationship('User', backref='workspace_collaborations')

# Canva - Design Tool
class DesignWorkspace(db.Model):
    __tablename__ = 'design_workspaces'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    workspace_type = db.Column(db.String(20), nullable=False)  # 'personal' or 'group'
    owner_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=True)  # For group workspaces
    template_type = db.Column(db.String(50), default='custom')  # poster, logo, presentation, etc.
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    owner = db.relationship('User', backref='owned_design_workspaces')
    server = db.relationship('Server', backref='design_workspaces')

class DesignProject(db.Model):
    __tablename__ = 'design_projects'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('design_workspaces.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    canvas_data = db.Column(db.Text, nullable=True)  # JSON data for canvas elements
    thumbnail_url = db.Column(db.String(500), nullable=True)
    width = db.Column(db.Integer, default=800)
    height = db.Column(db.Integer, default=600)
    created_by = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    workspace = db.relationship('DesignWorkspace', backref='projects')
    creator = db.relationship('User', backref='design_projects')

class DesignCollaborator(db.Model):
    __tablename__ = 'design_collaborators'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('design_workspaces.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    permission = db.Column(db.String(20), default='read')  # read, write, admin
    joined_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    workspace = db.relationship('DesignWorkspace', backref='design_collaborators')
    user = db.relationship('User', backref='design_collaborations')

# Opera Browser Sessions
class BrowserSession(db.Model):
    __tablename__ = 'browser_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    session_name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(2000), nullable=True)
    session_type = db.Column(db.String(20), nullable=False)  # 'personal' or 'group'
    owner_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=True)  # For group sessions
    is_active = db.Column(db.Boolean, default=True)
    shared_with_call = db.Column(db.Boolean, default=False)  # If shared during call
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    owner = db.relationship('User', backref='browser_sessions')
    server = db.relationship('Server', backref='browser_sessions')

class BrowserParticipant(db.Model):
    __tablename__ = 'browser_participants'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('browser_sessions.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    can_control = db.Column(db.Boolean, default=False)  # Can control the browser
    joined_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    session = db.relationship('BrowserSession', backref='participants')
    user = db.relationship('User', backref='browser_participations')

# File Storage for all tools
class ToolFile(db.Model):
    __tablename__ = 'tool_files'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)  # 'code', 'design', 'browser'
    workspace_id = db.Column(db.Integer, nullable=True)  # Generic workspace ID
    file_data = db.Column(db.LargeBinary, nullable=True)
    file_size = db.Column(db.Integer, default=0)
    mime_type = db.Column(db.String(100), nullable=True)
    owner_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    owner = db.relationship('User', backref='tool_files')

class MessageReaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.BigInteger, db.ForeignKey('messages.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    emoji = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    user = db.relationship('User', backref='reactions')
    
    # Unique constraint to prevent duplicate reactions
    __table_args__ = (db.UniqueConstraint('message_id', 'user_id', 'emoji', name='uq_message_user_emoji'),)

class MessageReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.BigInteger, db.ForeignKey('messages.id'), nullable=False)
    reporter_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    reason = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    reporter = db.relationship('User', backref='message_reports')

# Advanced Discord-like Models

class Role(db.Model):
    """Server roles with permissions"""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(7), default='#000000')  # Hex color
    hoist = db.Column(db.Boolean, default=False)  # Display separately
    icon_url = db.Column(db.String, nullable=True)  # Role icon
    unicode_emoji = db.Column(db.String(100), nullable=True)  # Unicode emoji
    position = db.Column(db.Integer, default=0)  # Role hierarchy position
    permissions = db.Column(db.BigInteger, default=0)  # Bitfield permissions
    managed = db.Column(db.Boolean, default=False)  # Bot managed
    mentionable = db.Column(db.Boolean, default=False)  # Can be mentioned
    tags = db.Column(db.Text, nullable=True)  # JSON role tags
    created_at = db.Column(db.DateTime, default=datetime.now)

class Thread(db.Model):
    """Message threads"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    owner_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    message_count = db.Column(db.Integer, default=0)
    member_count = db.Column(db.Integer, default=0)
    rate_limit_per_user = db.Column(db.Integer, default=0)
    thread_metadata = db.Column(db.Text, nullable=True)  # JSON metadata
    archived = db.Column(db.Boolean, default=False)
    archive_timestamp = db.Column(db.DateTime, nullable=True)
    auto_archive_duration = db.Column(db.Integer, default=4320)  # Minutes
    locked = db.Column(db.Boolean, default=False)
    invitable = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    owner = db.relationship('User', backref='owned_threads')

class CustomEmoji(db.Model):
    """Server custom emojis"""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    name = db.Column(db.String(32), nullable=False)
    image_url = db.Column(db.String, nullable=False)
    creator_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    require_colons = db.Column(db.Boolean, default=True)
    managed = db.Column(db.Boolean, default=False)
    animated = db.Column(db.Boolean, default=False)
    available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    creator = db.relationship('User', backref='created_emojis')

class Sticker(db.Model):
    """Server stickers"""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    name = db.Column(db.String(30), nullable=False)
    description = db.Column(db.String(100), nullable=True)
    tags = db.Column(db.String(200), nullable=False)  # Autocomplete tags
    asset_url = db.Column(db.String, nullable=False)
    pack_id = db.Column(db.String, nullable=True)  # Sticker pack ID
    available = db.Column(db.Boolean, default=True)
    format_type = db.Column(db.Integer, default=1)  # 1=PNG, 2=APNG, 3=LOTTIE
    created_at = db.Column(db.DateTime, default=datetime.now)

class ServerBan(db.Model):
    """Server bans"""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    reason = db.Column(db.String(512), nullable=True)
    moderator_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    expires_at = db.Column(db.DateTime, nullable=True)  # Temporary bans
    
    user = db.relationship('User', foreign_keys=[user_id], backref='server_bans')
    moderator = db.relationship('User', foreign_keys=[moderator_id], backref='moderated_bans')

class AuditLog(db.Model):
    """Server audit logs"""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    target_id = db.Column(db.String, nullable=True)  # Target user/channel/role ID
    action_type = db.Column(db.Integer, nullable=False)  # Action type enum
    options = db.Column(db.Text, nullable=True)  # JSON additional options
    reason = db.Column(db.String(512), nullable=True)
    changes = db.Column(db.Text, nullable=True)  # JSON before/after changes
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    user = db.relationship('User', backref='audit_actions')

class Webhook(db.Model):
    """Channel webhooks"""
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    avatar_url = db.Column(db.String, nullable=True)
    token = db.Column(db.String, nullable=False)
    application_id = db.Column(db.String, nullable=True)
    source_guild_id = db.Column(db.Integer, nullable=True)
    source_channel_id = db.Column(db.Integer, nullable=True)
    url = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    server = db.relationship('Server', backref='webhooks')

class UserPresence(db.Model):
    """User presence/activity status"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='offline')  # online, idle, dnd, invisible, offline
    activities = db.Column(db.Text, nullable=True)  # JSON array of activities
    client_status = db.Column(db.Text, nullable=True)  # JSON client platforms
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    user = db.relationship('User', backref='presence', uselist=False)

class Friendship(db.Model):
    """User friendships"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    friend_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, blocked
    created_at = db.Column(db.DateTime, default=datetime.now)
    accepted_at = db.Column(db.DateTime, nullable=True)
    
    user = db.relationship('User', foreign_keys=[user_id], backref='friendships_sent')
    friend = db.relationship('User', foreign_keys=[friend_id], backref='friendships_received')
    
    __table_args__ = (
        UniqueConstraint('user_id', 'friend_id', name='uq_friendship'),
    )

class UserSettings(db.Model):
    """User client settings"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False, unique=True)
    theme = db.Column(db.String(10), default='dark')  # dark, light
    language = db.Column(db.String(10), default='en-US')
    show_current_game = db.Column(db.Boolean, default=True)
    inline_attachment_media = db.Column(db.Boolean, default=True)
    inline_embed_media = db.Column(db.Boolean, default=True)
    gif_auto_play = db.Column(db.Boolean, default=True)
    render_embeds = db.Column(db.Boolean, default=True)
    render_reactions = db.Column(db.Boolean, default=True)
    animate_emoji = db.Column(db.Boolean, default=True)
    enable_tts_command = db.Column(db.Boolean, default=True)
    message_display_compact = db.Column(db.Boolean, default=False)
    convert_emoticons = db.Column(db.Boolean, default=True)
    explicit_content_filter = db.Column(db.Integer, default=0)  # 0=disabled, 1=friends, 2=everyone
    disable_games_tab = db.Column(db.Boolean, default=False)
    developer_mode = db.Column(db.Boolean, default=False)
    detect_platform_accounts = db.Column(db.Boolean, default=True)
    status_restrictions = db.Column(db.Text, nullable=True)  # JSON status restrictions
    custom_activity = db.Column(db.Text, nullable=True)  # JSON custom activity
    restricted_guilds = db.Column(db.Text, nullable=True)  # JSON restricted servers
    friend_source_flags = db.Column(db.Integer, default=14)  # Friend request sources
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    user = db.relationship('User', backref='settings', uselist=False)

class NotificationSettings(db.Model):
    """Notification preferences"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=True)
    notification_type = db.Column(db.String(20), default='all')  # all, mentions, nothing
    mobile_push = db.Column(db.Boolean, default=True)
    suppress_everyone = db.Column(db.Boolean, default=False)
    suppress_roles = db.Column(db.Boolean, default=False)
    muted_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    user = db.relationship('User', backref='notification_settings')
    server = db.relationship('Server', backref='notification_settings')
    channel = db.relationship('Channel', backref='notification_settings')

class Application(db.Model):
    """Bot applications"""
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String(32), nullable=False)
    icon_url = db.Column(db.String, nullable=True)
    description = db.Column(db.String(400), nullable=False)
    bot_public = db.Column(db.Boolean, default=True)
    bot_require_code_grant = db.Column(db.Boolean, default=False)
    terms_of_service_url = db.Column(db.String, nullable=True)
    privacy_policy_url = db.Column(db.String, nullable=True)
    owner_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    verify_key = db.Column(db.String, nullable=False)
    team_id = db.Column(db.String, nullable=True)
    guild_id = db.Column(db.Integer, nullable=True)
    primary_sku_id = db.Column(db.String, nullable=True)
    slug = db.Column(db.String, nullable=True)
    cover_image_url = db.Column(db.String, nullable=True)
    flags = db.Column(db.Integer, default=0)
    tags = db.Column(db.Text, nullable=True)  # JSON array
    install_params = db.Column(db.Text, nullable=True)  # JSON install parameters
    custom_install_url = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    owner = db.relationship('User', backref='owned_applications')

class SlashCommand(db.Model):
    """Application slash commands"""
    id = db.Column(db.String, primary_key=True)
    application_id = db.Column(db.String, db.ForeignKey('application.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=True)
    name = db.Column(db.String(32), nullable=False)
    description = db.Column(db.String(100), nullable=False)
    options = db.Column(db.Text, nullable=True)  # JSON command options
    default_member_permissions = db.Column(db.String, nullable=True)
    dm_permission = db.Column(db.Boolean, default=True)
    nsfw = db.Column(db.Boolean, default=False)
    version = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    application = db.relationship('Application', backref='slash_commands')
    server = db.relationship('Server', backref='slash_commands')

class Embed(db.Model):
    """Message embeds"""
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.BigInteger, db.ForeignKey('messages.id'), nullable=False)
    title = db.Column(db.String(256), nullable=True)
    embed_type = db.Column(db.String(20), default='rich')
    description = db.Column(db.String(4096), nullable=True)
    url = db.Column(db.String, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=True)
    color = db.Column(db.Integer, nullable=True)
    footer = db.Column(db.Text, nullable=True)  # JSON footer
    image = db.Column(db.Text, nullable=True)  # JSON image
    thumbnail = db.Column(db.Text, nullable=True)  # JSON thumbnail
    video = db.Column(db.Text, nullable=True)  # JSON video
    provider = db.Column(db.Text, nullable=True)  # JSON provider
    author = db.Column(db.Text, nullable=True)  # JSON author
    fields = db.Column(db.Text, nullable=True)  # JSON array of fields
    
    message = db.relationship('Message', backref='embeds')

class MessageAttachment(db.Model):
    """Message file attachments"""
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.BigInteger, db.ForeignKey('messages.id'), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    content_type = db.Column(db.String(100), nullable=True)
    size = db.Column(db.Integer, nullable=False)
    url = db.Column(db.String, nullable=False)
    proxy_url = db.Column(db.String, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    width = db.Column(db.Integer, nullable=True)
    ephemeral = db.Column(db.Boolean, default=False)
    description = db.Column(db.String(1024), nullable=True)
    
    message = db.relationship('Message', backref='attachments')

class VoiceState(db.Model):
    """User voice channel states"""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.String, nullable=False)
    deaf = db.Column(db.Boolean, default=False)
    mute = db.Column(db.Boolean, default=False)
    self_deaf = db.Column(db.Boolean, default=False)
    self_mute = db.Column(db.Boolean, default=False)
    self_stream = db.Column(db.Boolean, default=False)
    self_video = db.Column(db.Boolean, default=False)
    suppress = db.Column(db.Boolean, default=False)
    request_to_speak_timestamp = db.Column(db.DateTime, nullable=True)
    joined_at = db.Column(db.DateTime, default=datetime.now)
    
    server = db.relationship('Server', backref='voice_states')
    channel = db.relationship('Channel', backref='voice_states')
    user = db.relationship('User', backref='voice_states')

class ScheduledEvent(db.Model):
    """Server scheduled events"""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=True)
    creator_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(1000), nullable=True)
    scheduled_start_time = db.Column(db.DateTime, nullable=False)
    scheduled_end_time = db.Column(db.DateTime, nullable=True)
    privacy_level = db.Column(db.Integer, default=2)  # 1=public, 2=guild_only
    status = db.Column(db.Integer, default=1)  # 1=scheduled, 2=active, 3=completed, 4=cancelled
    entity_type = db.Column(db.Integer, nullable=False)  # 1=stage, 2=voice, 3=external
    entity_id = db.Column(db.String, nullable=True)
    entity_metadata = db.Column(db.Text, nullable=True)  # JSON metadata
    user_count = db.Column(db.Integer, default=0)
    image_url = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    server = db.relationship('Server', backref='scheduled_events')
    channel = db.relationship('Channel', backref='scheduled_events')
    creator = db.relationship('User', backref='created_events')

class Integration(db.Model):
    """Server integrations"""
    id = db.Column(db.String, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    integration_type = db.Column(db.String(20), nullable=False)  # twitch, youtube, discord, etc.
    enabled = db.Column(db.Boolean, default=True)
    syncing = db.Column(db.Boolean, default=False)
    role_id = db.Column(db.Integer, nullable=True)
    enable_emoticons = db.Column(db.Boolean, default=True)
    expire_behavior = db.Column(db.Integer, default=0)
    expire_grace_period = db.Column(db.Integer, default=1)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    account = db.Column(db.Text, nullable=True)  # JSON account info
    synced_at = db.Column(db.DateTime, nullable=True)
    subscriber_count = db.Column(db.Integer, default=0)
    revoked = db.Column(db.Boolean, default=False)
    application = db.Column(db.Text, nullable=True)  # JSON application info
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    server = db.relationship('Server', backref='integrations')
    user = db.relationship('User', backref='integrations')

# Analytics and tracking models for intelligent admin dashboard
class UserActivity(db.Model):
    __tablename__ = 'user_activity'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # login, logout, message_sent, server_joined, etc.
    activity_data = db.Column(db.Text, nullable=True)  # JSON data for additional context
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4/IPv6 support
    user_agent = db.Column(db.Text, nullable=True)
    session_id = db.Column(db.String(255), nullable=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    
    # Relationships
    user = db.relationship('User', backref='activities')
    server = db.relationship('Server', backref='activities')
    channel = db.relationship('Channel', backref='activities')
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_user_activity_type', 'user_id', 'activity_type'),
        Index('idx_activity_created_at', 'created_at'),
        Index('idx_activity_type_date', 'activity_type', 'created_at'),
        Index('idx_server_activity', 'server_id', 'created_at'),
    )

class SystemMetrics(db.Model):
    __tablename__ = 'system_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    metric_name = db.Column(db.String(100), nullable=False)  # active_users, messages_per_hour, etc.
    metric_value = db.Column(db.Float, nullable=False)
    metric_data = db.Column(db.Text, nullable=True)  # JSON for complex metrics
    recorded_at = db.Column(db.DateTime, default=datetime.now, index=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_metric_name_date', 'metric_name', 'recorded_at'),
    )

class UserSession(db.Model):
    __tablename__ = 'user_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.String(255), unique=True, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.now)
    last_activity = db.Column(db.DateTime, default=datetime.now)
    ended_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    device_type = db.Column(db.String(50), nullable=True)  # mobile, desktop, tablet
    browser = db.Column(db.String(100), nullable=True)
    os = db.Column(db.String(100), nullable=True)
    
    # Relationships
    user = db.relationship('User', backref='sessions')
    
    # Indexes
    __table_args__ = (
        Index('idx_user_sessions', 'user_id', 'is_active'),
        Index('idx_session_activity', 'last_activity'),
    )
