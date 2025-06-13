import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import hashlib
import uuid
import base64
import sqlite3
import os
from dataclasses import dataclass
from typing import List, Optional, Dict
import json

# Page configuration
st.set_page_config(
    page_title="CommunicationX - Streamlit",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database setup for Streamlit version
DATABASE_FILE = "communicationx_streamlit.db"

@dataclass
class User:
    id: str
    username: str
    email: str
    password_hash: str
    first_name: str = ""
    last_name: str = ""
    status: str = "online"
    created_at: str = ""

@dataclass
class Server:
    id: int
    name: str
    description: str
    owner_id: str
    is_public: bool = True
    created_at: str = ""

@dataclass
class Channel:
    id: int
    name: str
    server_id: int
    created_at: str = ""

@dataclass
class Message:
    id: int
    content: str
    author_id: str
    channel_id: int
    created_at: str
    message_type: str = "text"

@dataclass
class DirectMessage:
    id: int
    content: str
    sender_id: str
    recipient_id: str
    created_at: str

@dataclass
class Call:
    id: int
    caller_id: str
    recipient_id: str
    call_type: str
    status: str
    started_at: str

# Database functions
def init_database():
    """Initialize SQLite database for Streamlit version"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            status TEXT DEFAULT 'online',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Servers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            owner_id TEXT NOT NULL,
            is_public BOOLEAN DEFAULT TRUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users (id)
        )
    """)
    
    # Channels table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            server_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (server_id) REFERENCES servers (id)
        )
    """)
    
    # Messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            author_id TEXT NOT NULL,
            channel_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            message_type TEXT DEFAULT 'text',
            FOREIGN KEY (author_id) REFERENCES users (id),
            FOREIGN KEY (channel_id) REFERENCES channels (id)
        )
    """)
    
    # Direct messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS direct_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            recipient_id TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (recipient_id) REFERENCES users (id)
        )
    """)
    
    # Server memberships table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS server_memberships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            server_id INTEGER NOT NULL,
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (server_id) REFERENCES servers (id),
            UNIQUE(user_id, server_id)
        )
    """)
    
    # Calls table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caller_id TEXT NOT NULL,
            recipient_id TEXT NOT NULL,
            call_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (caller_id) REFERENCES users (id),
            FOREIGN KEY (recipient_id) REFERENCES users (id)
        )
    """)
    
    # Message reactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS message_reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            emoji TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES messages (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(message_id, user_id, emoji)
        )
    """)
    
    # DM reactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dm_reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dm_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            emoji TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (dm_id) REFERENCES direct_messages (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(dm_id, user_id, emoji)
        )
    """)
    
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate user"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    password_hash = hash_password(password)
    cursor.execute("""
        SELECT id, username, email, password_hash, first_name, last_name, status, created_at
        FROM users WHERE username = ? AND password_hash = ?
    """, (username, password_hash))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return User(*result)
    return None

def register_user(username: str, email: str, password: str, first_name: str = "", last_name: str = "") -> tuple:
    """Register new user"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
    if cursor.fetchone():
        conn.close()
        return None, "Username or email already exists"
    
    # Create user
    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)
    
    try:
        cursor.execute("""
            INSERT INTO users (id, username, email, password_hash, first_name, last_name)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, username, email, password_hash, first_name, last_name))
        
        # Auto-join public servers
        cursor.execute("SELECT id FROM servers WHERE is_public = TRUE")
        public_servers = cursor.fetchall()
        
        for server_id_tuple in public_servers:
            server_id = server_id_tuple[0]
            cursor.execute("""
                INSERT OR IGNORE INTO server_memberships (user_id, server_id)
                VALUES (?, ?)
            """, (user_id, server_id))
        
        conn.commit()
        conn.close()
        
        user = User(user_id, username, email, password_hash, first_name, last_name)
        return user, "Success"
    except Exception as e:
        conn.close()
        return None, f"Registration failed: {str(e)}"

def get_user_servers(user_id: str) -> List[Server]:
    """Get servers for user"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT s.id, s.name, s.description, s.owner_id, s.is_public, s.created_at
        FROM servers s
        JOIN server_memberships sm ON s.id = sm.server_id
        WHERE sm.user_id = ?
        ORDER BY s.name
    """, (user_id,))
    
    servers = [Server(*row) for row in cursor.fetchall()]
    conn.close()
    return servers

def get_server_channels(server_id: int) -> List[Channel]:
    """Get channels for server"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, server_id, created_at
        FROM channels
        WHERE server_id = ?
        ORDER BY name
    """, (server_id,))
    
    channels = [Channel(*row) for row in cursor.fetchall()]
    conn.close()
    return channels

def get_channel_messages(channel_id: int, limit: int = 50) -> List[tuple]:
    """Get messages for channel with author info"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT m.id, m.content, m.author_id, m.channel_id, m.created_at, m.message_type,
               u.username, u.status
        FROM messages m
        JOIN users u ON m.author_id = u.id
        WHERE m.channel_id = ?
        ORDER BY m.created_at DESC
        LIMIT ?
    """, (channel_id, limit))
    
    messages = cursor.fetchall()
    conn.close()
    return list(reversed(messages))

def send_message(content: str, author_id: str, channel_id: int) -> bool:
    """Send message to channel"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO messages (content, author_id, channel_id)
            VALUES (?, ?, ?)
        """, (content, author_id, channel_id))
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False

def get_dm_conversations(user_id: str) -> List[tuple]:
    """Get DM conversations for user"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT 
            CASE 
                WHEN dm.sender_id = ? THEN dm.recipient_id 
                ELSE dm.sender_id 
            END as other_user_id,
            u.username, u.status,
            MAX(dm.created_at) as last_message_time
        FROM direct_messages dm
        JOIN users u ON (
            CASE 
                WHEN dm.sender_id = ? THEN dm.recipient_id = u.id
                ELSE dm.sender_id = u.id
            END
        )
        WHERE dm.sender_id = ? OR dm.recipient_id = ?
        GROUP BY other_user_id, u.username, u.status
        ORDER BY last_message_time DESC
    """, (user_id, user_id, user_id, user_id))
    
    conversations = cursor.fetchall()
    conn.close()
    return conversations

def get_direct_messages(user1_id: str, user2_id: str, limit: int = 50) -> List[tuple]:
    """Get direct messages between two users"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT dm.id, dm.content, dm.sender_id, dm.recipient_id, dm.created_at,
               u.username, u.status
        FROM direct_messages dm
        JOIN users u ON dm.sender_id = u.id
        WHERE (dm.sender_id = ? AND dm.recipient_id = ?) 
           OR (dm.sender_id = ? AND dm.recipient_id = ?)
        ORDER BY dm.created_at DESC
        LIMIT ?
    """, (user1_id, user2_id, user2_id, user1_id, limit))
    
    messages = cursor.fetchall()
    conn.close()
    return list(reversed(messages))

def send_direct_message(content: str, sender_id: str, recipient_id: str) -> bool:
    """Send direct message"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO direct_messages (content, sender_id, recipient_id)
            VALUES (?, ?, ?)
        """, (content, sender_id, recipient_id))
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False

def create_server(name: str, description: str, owner_id: str, is_public: bool = True) -> Optional[int]:
    """Create new server"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO servers (name, description, owner_id, is_public)
            VALUES (?, ?, ?, ?)
        """, (name, description, owner_id, is_public))
        
        server_id = cursor.lastrowid
        
        # Create default channel
        cursor.execute("""
            INSERT INTO channels (name, server_id)
            VALUES (?, ?)
        """, ("general", server_id))
        
        # Add owner as member
        cursor.execute("""
            INSERT INTO server_memberships (user_id, server_id)
            VALUES (?, ?)
        """, (owner_id, server_id))
        
        conn.commit()
        conn.close()
        return server_id
    except Exception:
        conn.close()
        return None

def create_channel(name: str, server_id: int) -> Optional[int]:
    """Create new channel in server"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO channels (name, server_id)
            VALUES (?, ?)
        """, (name, server_id))
        
        channel_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return channel_id
    except Exception:
        conn.close()
        return None

def delete_channel(channel_id: int, user_id: str) -> bool:
    """Delete channel if user is server owner"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        # Check if user is server owner
        cursor.execute("""
            SELECT s.owner_id FROM servers s
            JOIN channels c ON s.id = c.server_id
            WHERE c.id = ?
        """, (channel_id,))
        
        result = cursor.fetchone()
        if not result or result[0] != user_id:
            conn.close()
            return False
        
        # Delete all messages in channel first
        cursor.execute("DELETE FROM messages WHERE channel_id = ?", (channel_id,))
        
        # Delete the channel
        cursor.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False

def get_server_owner(server_id: int) -> Optional[str]:
    """Get server owner ID"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT owner_id FROM servers WHERE id = ?", (server_id,))
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None

def get_all_users() -> List[User]:
    """Get all users for DM selection"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, username, email, password_hash, first_name, last_name, status, created_at
        FROM users
        ORDER BY username
    """)
    
    users = [User(*row) for row in cursor.fetchall()]
    conn.close()
    return users

# Message management functions
def delete_message(message_id: int, user_id: str) -> bool:
    """Delete message if user is author"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        # Check if user is message author
        cursor.execute("SELECT author_id FROM messages WHERE id = ?", (message_id,))
        result = cursor.fetchone()
        
        if not result or result[0] != user_id:
            conn.close()
            return False
        
        # Delete message and reactions
        cursor.execute("DELETE FROM message_reactions WHERE message_id = ?", (message_id,))
        cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False

def delete_dm(dm_id: int, user_id: str) -> bool:
    """Delete direct message if user is sender"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        # Check if user is sender
        cursor.execute("SELECT sender_id FROM direct_messages WHERE id = ?", (dm_id,))
        result = cursor.fetchone()
        
        if not result or result[0] != user_id:
            conn.close()
            return False
        
        # Delete DM and reactions
        cursor.execute("DELETE FROM dm_reactions WHERE dm_id = ?", (dm_id,))
        cursor.execute("DELETE FROM direct_messages WHERE id = ?", (dm_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False

def add_message_reaction(message_id: int, user_id: str, emoji: str) -> bool:
    """Add or remove reaction to message"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        # Check if reaction already exists
        cursor.execute("""
            SELECT id FROM message_reactions 
            WHERE message_id = ? AND user_id = ? AND emoji = ?
        """, (message_id, user_id, emoji))
        
        existing = cursor.fetchone()
        
        if existing:
            # Remove reaction
            cursor.execute("""
                DELETE FROM message_reactions 
                WHERE message_id = ? AND user_id = ? AND emoji = ?
            """, (message_id, user_id, emoji))
        else:
            # Add reaction
            cursor.execute("""
                INSERT INTO message_reactions (message_id, user_id, emoji)
                VALUES (?, ?, ?)
            """, (message_id, user_id, emoji))
        
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False

def add_dm_reaction(dm_id: int, user_id: str, emoji: str) -> bool:
    """Add or remove reaction to direct message"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        # Check if reaction already exists
        cursor.execute("""
            SELECT id FROM dm_reactions 
            WHERE dm_id = ? AND user_id = ? AND emoji = ?
        """, (dm_id, user_id, emoji))
        
        existing = cursor.fetchone()
        
        if existing:
            # Remove reaction
            cursor.execute("""
                DELETE FROM dm_reactions 
                WHERE dm_id = ? AND user_id = ? AND emoji = ?
            """, (dm_id, user_id, emoji))
        else:
            # Add reaction
            cursor.execute("""
                INSERT INTO dm_reactions (dm_id, user_id, emoji)
                VALUES (?, ?, ?)
            """, (dm_id, user_id, emoji))
        
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False

def get_message_reactions(message_id: int) -> Dict[str, int]:
    """Get reaction counts for message"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT emoji, COUNT(*) as count
        FROM message_reactions
        WHERE message_id = ?
        GROUP BY emoji
    """, (message_id,))
    
    reactions = {emoji: count for emoji, count in cursor.fetchall()}
    conn.close()
    return reactions

def get_dm_reactions(dm_id: int) -> Dict[str, int]:
    """Get reaction counts for direct message"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT emoji, COUNT(*) as count
        FROM dm_reactions
        WHERE dm_id = ?
        GROUP BY emoji
    """, (dm_id,))
    
    reactions = {emoji: count for emoji, count in cursor.fetchall()}
    conn.close()
    return reactions

def forward_message_to_dm(message_id: int, sender_id: str, recipient_id: str) -> bool:
    """Forward message content to direct message"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        # Get original message content
        cursor.execute("SELECT content FROM messages WHERE id = ?", (message_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return False
        
        content = f"[Forwarded] {result[0]}"
        
        # Send as DM
        cursor.execute("""
            INSERT INTO direct_messages (content, sender_id, recipient_id)
            VALUES (?, ?, ?)
        """, (content, sender_id, recipient_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False

def forward_dm_to_dm(dm_id: int, sender_id: str, recipient_id: str) -> bool:
    """Forward DM content to another direct message"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        # Get original DM content
        cursor.execute("SELECT content FROM direct_messages WHERE id = ?", (dm_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return False
        
        content = f"[Forwarded] {result[0]}"
        
        # Send as new DM
        cursor.execute("""
            INSERT INTO direct_messages (content, sender_id, recipient_id)
            VALUES (?, ?, ?)
        """, (content, sender_id, recipient_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False

# Initialize session state
def init_session_state():
    """Initialize Streamlit session state"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'current_server' not in st.session_state:
        st.session_state.current_server = None
    if 'current_channel' not in st.session_state:
        st.session_state.current_channel = None
    if 'dm_recipient' not in st.session_state:
        st.session_state.dm_recipient = None
    if 'page' not in st.session_state:
        st.session_state.page = 'servers'

# Custom CSS
def load_css():
    """Load custom CSS for Discord-like theme"""
    st.markdown("""
    <style>
        .main {
            background-color: #36393f;
            color: #dcddde;
        }
        
        .sidebar .sidebar-content {
            background-color: #2f3136;
        }
        
        .message-container {
            background-color: #40444b;
            padding: 12px 16px;
            border-radius: 8px;
            margin: 8px 0;
            border-left: 3px solid #7289da;
        }
        
        .message-author {
            font-weight: bold;
            color: #7289da;
            margin-bottom: 4px;
            font-size: 0.9em;
        }
        
        .message-timestamp {
            font-size: 0.75em;
            color: #72767d;
            margin-left: 8px;
        }
        
        .message-content {
            margin-top: 4px;
            line-height: 1.4;
        }
        
        .status-online { color: #43b581; }
        .status-away { color: #faa61a; }
        .status-busy { color: #f04747; }
        .status-invisible { color: #747f8d; }
        
        .stButton > button {
            background-color: #7289da;
            color: white;
            border: none;
            border-radius: 4px;
        }
        
        .stButton > button:hover {
            background-color: #677bc4;
        }
        
        .server-button {
            width: 100%;
            margin: 2px 0;
        }
        
        .channel-button {
            width: 100%;
            margin: 1px 0;
            font-size: 0.9em;
        }
    </style>
    """, unsafe_allow_html=True)

# Authentication page
def show_auth_page():
    """Show login/register page"""
    # Display logo
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        try:
            st.image("static/assets/CommunicationX.png", width=150)
        except:
            st.markdown("### 🚀 CommunicationX")
    
    st.markdown("<h1 style='text-align: center;'>Join CommunicationX</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #888;'>Enter your credentials to login or create a new account</p>", unsafe_allow_html=True)
    
    # Center the form
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("auth_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            email = st.text_input("Email", placeholder="Enter your email")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            continue_btn = st.form_submit_button("Continue", use_container_width=True)
            
            if continue_btn:
                if username and email and password:
                    # Check if user exists with matching credentials
                    existing_user = authenticate_user(username, password)
                    
                    if existing_user and existing_user.email == email:
                        # User exists and credentials match
                        st.session_state.authenticated = True
                        st.session_state.user = existing_user
                        st.success(f"Welcome back, {username}!")
                        st.rerun()
                    else:
                        # Check if username or email already exists
                        conn = sqlite3.connect(DATABASE_FILE)
                        cursor = conn.cursor()
                        
                        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                        username_exists = cursor.fetchone()
                        
                        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
                        email_exists = cursor.fetchone()
                        
                        conn.close()
                        
                        if username_exists:
                            st.error("Username already exists")
                        elif email_exists:
                            st.error("Email already exists")
                        else:
                            # Create new user
                            success, message = register_user(username, email, password, username, "")
                            if success:
                                user = authenticate_user(username, password)
                                if user:
                                    st.session_state.authenticated = True
                                    st.session_state.user = user
                                    st.success(f"Account created successfully! Welcome, {username}!")
                                    st.rerun()
                            else:
                                st.error(message)
                else:
                    st.error("Please fill all fields")
    
    st.markdown("<p style='text-align: center; margin-top: 2rem; color: #666; font-size: 0.9rem;'>If you have an account, enter your credentials to login.<br>If you don't have an account, we'll create one for you automatically.</p>", unsafe_allow_html=True)

# Main application pages
def show_servers_page():
    """Show servers and channels"""
    st.header("🏰 Servers")
    
    servers = get_user_servers(st.session_state.user.id)
    
    if not servers:
        st.info("No servers found. Create your first server!")
    
    # Server selection
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if servers:
            server_options = {f"{server.name}": server.id for server in servers}
            selected_server_name = st.selectbox("Select Server", list(server_options.keys()))
            
            if selected_server_name:
                selected_server_id = server_options[selected_server_name]
                st.session_state.current_server = selected_server_id
                
                # Show channels
                channels = get_server_channels(selected_server_id)
                if channels:
                    st.subheader("📋 Channels")
                    
                    # Channel management for server owners
                    server_owner = get_server_owner(selected_server_id)
                    is_owner = server_owner == st.session_state.user.id
                    
                    if is_owner:
                        col_ch1, col_ch2 = st.columns([3, 1])
                        with col_ch1:
                            channel_options = {f"# {channel.name}": channel.id for channel in channels}
                            selected_channel_name = st.selectbox("Select Channel", list(channel_options.keys()))
                        with col_ch2:
                            st.write("")  # Spacing
                            if st.button("➕ Add", key="add_channel"):
                                st.session_state.show_create_channel = True
                    else:
                        channel_options = {f"# {channel.name}": channel.id for channel in channels}
                        selected_channel_name = st.selectbox("Select Channel", list(channel_options.keys()))
                    
                    if selected_channel_name:
                        selected_channel_id = channel_options[selected_channel_name]
                        st.session_state.current_channel = selected_channel_id
                        
                        # Channel actions for owners
                        if is_owner and len(channels) > 1:  # Don't allow deleting the last channel
                            if st.button(f"🗑️ Delete # {selected_channel_name.replace('# ', '')}", key="delete_channel"):
                                if delete_channel(selected_channel_id, st.session_state.user.id):
                                    st.success("Channel deleted!")
                                    st.session_state.current_channel = None
                                    st.rerun()
                                else:
                                    st.error("Failed to delete channel")
                        
                        # Show messages
                        show_channel_messages(selected_channel_id)
    
    with col2:
        st.subheader("Actions")
        if st.button("Create Server", use_container_width=True):
            st.session_state.show_create_server = True
        
        if st.button("Refresh", use_container_width=True):
            st.rerun()

def show_channel_messages(channel_id: int):
    """Show messages for selected channel"""
    st.markdown("---")
    st.subheader("💬 Messages")
    
    # Reply context
    if 'reply_to_message' in st.session_state and st.session_state.reply_to_message:
        st.info(f"Replying to message: {st.session_state.reply_to_message['content'][:50]}...")
        if st.button("Cancel Reply"):
            del st.session_state.reply_to_message
            st.rerun()
    
    # Message input
    with st.form("send_message_form", clear_on_submit=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            message_content = st.text_area("Type your message...", height=80, key="message_input")
        with col2:
            st.write("")  # Spacing
            send_btn = st.form_submit_button("Send", use_container_width=True)
        
        if send_btn and message_content.strip():
            # Handle reply
            if 'reply_to_message' in st.session_state and st.session_state.reply_to_message:
                reply_content = f"@{st.session_state.reply_to_message['username']}: {message_content.strip()}"
                del st.session_state.reply_to_message
            else:
                reply_content = message_content.strip()
            
            if send_message(reply_content, st.session_state.user.id, channel_id):
                st.success("Message sent!")
                st.rerun()
            else:
                st.error("Failed to send message")
    
    # Display messages
    messages = get_channel_messages(channel_id)
    
    if messages:
        st.markdown("### Recent Messages")
        for msg_data in messages:
            msg_id, content, author_id, channel_id, created_at, msg_type, username, status = msg_data
            
            timestamp = created_at.split('.')[0] if '.' in created_at else created_at
            status_icon = {"online": "🟢", "away": "🟡", "busy": "🔴", "invisible": "⚫"}.get(status, "⚫")
            
            # Get reactions for this message
            reactions = get_message_reactions(msg_id)
            reactions_display = " ".join([f"{emoji} {count}" for emoji, count in reactions.items()])
            
            st.markdown(f"""
            <div class="message-container">
                <div class="message-author">
                    {status_icon} {username}
                    <span class="message-timestamp">{timestamp}</span>
                </div>
                <div class="message-content">{content}</div>
                {f'<div class="reactions">{reactions_display}</div>' if reactions else ''}
            </div>
            """, unsafe_allow_html=True)
            
            # Message actions
            col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
            
            # Emoji reactions
            with col1:
                emoji_options = ["👍", "❤️", "😂", "😮", "😢", "😡", "🎉", "👏", "🔥", "💯"]
                selected_emoji = st.selectbox("React", [""] + emoji_options, key=f"emoji_{msg_id}")
                if selected_emoji:
                    if add_message_reaction(msg_id, st.session_state.user.id, selected_emoji):
                        st.rerun()
            
            # Reply
            with col2:
                if st.button("↩️ Reply", key=f"reply_{msg_id}"):
                    st.session_state.reply_to_message = {
                        'id': msg_id,
                        'content': content,
                        'username': username
                    }
                    st.rerun()
            
            # Forward
            with col3:
                if st.button("↗️ Forward", key=f"forward_{msg_id}"):
                    st.session_state.forward_message = msg_id
                    st.session_state.show_forward_modal = True
                    st.rerun()
            
            # Delete (only for message author)
            if author_id == st.session_state.user.id:
                with col4:
                    if st.button("🗑️ Delete", key=f"delete_{msg_id}"):
                        if delete_message(msg_id, st.session_state.user.id):
                            st.success("Message deleted!")
                            st.rerun()
                        else:
                            st.error("Failed to delete message")
            
            st.markdown("---")
    else:
        st.info("No messages yet. Start the conversation!")
    
    # Forward modal
    if 'show_forward_modal' in st.session_state and st.session_state.show_forward_modal:
        show_forward_modal()

def show_dm_page():
    """Show direct messages"""
    st.header("💬 Direct Messages")
    
    # Get conversations
    conversations = get_dm_conversations(st.session_state.user.id)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Conversations")
        
        if conversations:
            for conv in conversations:
                other_user_id, username, status, last_message_time = conv
                status_icon = {"online": "🟢", "away": "🟡", "busy": "🔴", "invisible": "⚫"}.get(status, "⚫")
                
                if st.button(f"{status_icon} {username}", key=f"dm_conv_{other_user_id}", use_container_width=True):
                    st.session_state.dm_recipient = other_user_id
                    st.rerun()
        else:
            st.info("No conversations yet")
        
        # Start new conversation
        st.markdown("---")
        st.subheader("Start New Chat")
        all_users = get_all_users()
        user_options = {f"{user.username}": user.id for user in all_users if user.id != st.session_state.user.id}
        
        if user_options:
            selected_user = st.selectbox("Select User", list(user_options.keys()))
            if st.button("Start Chat", use_container_width=True):
                st.session_state.dm_recipient = user_options[selected_user]
                st.rerun()
    
    with col2:
        if st.session_state.dm_recipient:
            show_direct_messages()
        else:
            st.info("Select a conversation to view messages")

def show_direct_messages():
    """Show direct messages with selected user"""
    # Get recipient info
    all_users = get_all_users()
    recipient = next((user for user in all_users if user.id == st.session_state.dm_recipient), None)
    
    if not recipient:
        st.error("User not found")
        return
    
    st.subheader(f"Chat with {recipient.username}")
    status_icon = {"online": "🟢", "away": "🟡", "busy": "🔴", "invisible": "⚫"}.get(recipient.status, "⚫")
    st.caption(f"Status: {status_icon} {recipient.status.title()}")
    
    # Reply context for DMs
    if 'reply_to_dm' in st.session_state and st.session_state.reply_to_dm:
        st.info(f"Replying to message: {st.session_state.reply_to_dm['content'][:50]}...")
        if st.button("Cancel Reply", key="cancel_dm_reply"):
            del st.session_state.reply_to_dm
            st.rerun()
    
    # Message input
    with st.form("send_dm_form", clear_on_submit=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            dm_content = st.text_area("Type your message...", height=80, key="dm_input")
        with col2:
            st.write("")  # Spacing
            send_dm_btn = st.form_submit_button("Send", use_container_width=True)
        
        if send_dm_btn and dm_content.strip():
            # Handle reply for DMs
            if 'reply_to_dm' in st.session_state and st.session_state.reply_to_dm:
                reply_content = f"@{st.session_state.reply_to_dm['username']}: {dm_content.strip()}"
                del st.session_state.reply_to_dm
            else:
                reply_content = dm_content.strip()
            
            if send_direct_message(reply_content, st.session_state.user.id, st.session_state.dm_recipient):
                st.success("Message sent!")
                st.rerun()
            else:
                st.error("Failed to send message")
    
    # Display messages
    messages = get_direct_messages(st.session_state.user.id, st.session_state.dm_recipient)
    
    if messages:
        st.markdown("### Messages")
        for msg_data in messages:
            msg_id, content, sender_id, recipient_id, created_at, username, status = msg_data
            
            timestamp = created_at.split('.')[0] if '.' in created_at else created_at
            status_icon = {"online": "🟢", "away": "🟡", "busy": "🔴", "invisible": "⚫"}.get(status, "⚫")
            
            # Get reactions for this DM
            reactions = get_dm_reactions(msg_id)
            reactions_display = " ".join([f"{emoji} {count}" for emoji, count in reactions.items()])
            
            st.markdown(f"""
            <div class="message-container">
                <div class="message-author">
                    {status_icon} {username}
                    <span class="message-timestamp">{timestamp}</span>
                </div>
                <div class="message-content">{content}</div>
                {f'<div class="reactions">{reactions_display}</div>' if reactions else ''}
            </div>
            """, unsafe_allow_html=True)
            
            # DM Message actions
            col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
            
            # Emoji reactions for DMs
            with col1:
                emoji_options = ["👍", "❤️", "😂", "😮", "😢", "😡", "🎉", "👏", "🔥", "💯"]
                selected_emoji = st.selectbox("React", [""] + emoji_options, key=f"dm_emoji_{msg_id}")
                if selected_emoji:
                    if add_dm_reaction(msg_id, st.session_state.user.id, selected_emoji):
                        st.rerun()
            
            # Reply for DMs
            with col2:
                if st.button("↩️ Reply", key=f"dm_reply_{msg_id}"):
                    st.session_state.reply_to_dm = {
                        'id': msg_id,
                        'content': content,
                        'username': username
                    }
                    st.rerun()
            
            # Forward DM
            with col3:
                if st.button("↗️ Forward", key=f"dm_forward_{msg_id}"):
                    st.session_state.forward_dm = msg_id
                    st.session_state.show_forward_dm_modal = True
                    st.rerun()
            
            # Delete DM (only for sender)
            if sender_id == st.session_state.user.id:
                with col4:
                    if st.button("🗑️ Delete", key=f"dm_delete_{msg_id}"):
                        if delete_dm(msg_id, st.session_state.user.id):
                            st.success("Message deleted!")
                            st.rerun()
                        else:
                            st.error("Failed to delete message")
            
            st.markdown("---")
    else:
        st.info("No messages yet. Start the conversation!")

def show_create_server_modal():
    """Show create server form"""
    if 'show_create_server' in st.session_state and st.session_state.show_create_server:
        st.markdown("---")
        st.subheader("Create New Server")
        
        with st.form("create_server_form"):
            server_name = st.text_input("Server Name*")
            server_description = st.text_area("Description")
            is_public = st.checkbox("Public Server", value=True)
            
            col1, col2 = st.columns(2)
            with col1:
                create_btn = st.form_submit_button("Create", use_container_width=True)
            with col2:
                cancel_btn = st.form_submit_button("Cancel", use_container_width=True)
            
            if create_btn and server_name:
                server_id = create_server(server_name, server_description, st.session_state.user.id, is_public)
                if server_id:
                    st.success(f"Server '{server_name}' created!")
                    del st.session_state.show_create_server
                    st.rerun()
                else:
                    st.error("Failed to create server")
            
            if cancel_btn:
                del st.session_state.show_create_server
                st.rerun()

def show_create_channel_modal():
    """Show create channel form"""
    if 'show_create_channel' in st.session_state and st.session_state.show_create_channel:
        st.markdown("---")
        st.subheader("Create New Channel")
        
        with st.form("create_channel_form"):
            channel_name = st.text_input("Channel Name*", placeholder="general, random, announcements...")
            
            col1, col2 = st.columns(2)
            with col1:
                create_btn = st.form_submit_button("Create Channel", use_container_width=True)
            with col2:
                cancel_btn = st.form_submit_button("Cancel", use_container_width=True)
            
            if create_btn and channel_name and st.session_state.current_server:
                # Clean channel name (remove # and spaces, lowercase)
                clean_name = channel_name.replace('#', '').replace(' ', '-').lower()
                channel_id = create_channel(clean_name, st.session_state.current_server)
                if channel_id:
                    st.success(f"Channel '#{clean_name}' created!")
                    del st.session_state.show_create_channel
                    st.rerun()
                else:
                    st.error("Failed to create channel")
            
            if cancel_btn:
                del st.session_state.show_create_channel
                st.rerun()

def show_forward_modal():
    """Show forward message modal"""
    if 'show_forward_modal' in st.session_state and st.session_state.show_forward_modal:
        st.markdown("---")
        st.subheader("Forward Message")
        
        all_users = get_all_users()
        user_options = {f"{user.username}": user.id for user in all_users if user.id != st.session_state.user.id}
        
        with st.form("forward_message_form"):
            recipient = st.selectbox("Select recipient", list(user_options.keys()))
            
            col1, col2 = st.columns(2)
            with col1:
                forward_btn = st.form_submit_button("Forward", use_container_width=True)
            with col2:
                cancel_btn = st.form_submit_button("Cancel", use_container_width=True)
            
            if forward_btn and recipient and st.session_state.forward_message:
                recipient_id = user_options[recipient]
                if forward_message_to_dm(st.session_state.forward_message, st.session_state.user.id, recipient_id):
                    st.success(f"Message forwarded to {recipient}!")
                    del st.session_state.forward_message
                    del st.session_state.show_forward_modal
                    st.rerun()
                else:
                    st.error("Failed to forward message")
            
            if cancel_btn:
                if 'forward_message' in st.session_state:
                    del st.session_state.forward_message
                del st.session_state.show_forward_modal
                st.rerun()

def show_forward_dm_modal():
    """Show forward DM modal"""
    if 'show_forward_dm_modal' in st.session_state and st.session_state.show_forward_dm_modal:
        st.markdown("---")
        st.subheader("Forward Message")
        
        all_users = get_all_users()
        user_options = {f"{user.username}": user.id for user in all_users if user.id != st.session_state.user.id}
        
        with st.form("forward_dm_form"):
            recipient = st.selectbox("Select recipient", list(user_options.keys()))
            
            col1, col2 = st.columns(2)
            with col1:
                forward_btn = st.form_submit_button("Forward", use_container_width=True)
            with col2:
                cancel_btn = st.form_submit_button("Cancel", use_container_width=True)
            
            if forward_btn and recipient and st.session_state.forward_dm:
                recipient_id = user_options[recipient]
                if forward_dm_to_dm(st.session_state.forward_dm, st.session_state.user.id, recipient_id):
                    st.success(f"Message forwarded to {recipient}!")
                    del st.session_state.forward_dm
                    del st.session_state.show_forward_dm_modal
                    st.rerun()
                else:
                    st.error("Failed to forward message")
            
            if cancel_btn:
                if 'forward_dm' in st.session_state:
                    del st.session_state.forward_dm
                del st.session_state.show_forward_dm_modal
                st.rerun()

def show_sidebar():
    """Show sidebar navigation"""
    with st.sidebar:
        st.markdown(f"### Welcome, {st.session_state.user.username}!")
        
        # Status selection
        status_options = ["online", "away", "busy", "invisible"]
        current_status = st.selectbox("Status", status_options, 
                                    index=status_options.index(st.session_state.user.status))
        
        st.markdown("---")
        
        # Navigation
        page = st.radio("Navigation", ["Servers", "Direct Messages", "Profile"])
        
        if page == "Servers":
            st.session_state.page = 'servers'
        elif page == "Direct Messages":
            st.session_state.page = 'dm'
        elif page == "Profile":
            st.session_state.page = 'profile'
        
        st.markdown("---")
        
        # Logout
        if st.button("Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

def show_profile_page():
    """Show user profile"""
    st.header("👤 Profile")
    
    user = st.session_state.user
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("User Information")
        st.text(f"Username: {user.username}")
        st.text(f"Email: {user.email}")
        if user.first_name:
            st.text(f"Name: {user.first_name} {user.last_name}")
        st.text(f"Status: {user.status}")
        st.text(f"Member since: {user.created_at.split(' ')[0] if user.created_at else 'Unknown'}")
    
    with col2:
        st.subheader("Statistics")
        
        # Get user stats
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM messages WHERE author_id = ?", (user.id,))
        message_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM direct_messages WHERE sender_id = ?", (user.id,))
        dm_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM server_memberships WHERE user_id = ?", (user.id,))
        server_count = cursor.fetchone()[0]
        
        conn.close()
        
        st.metric("Messages Sent", message_count)
        st.metric("Direct Messages", dm_count)
        st.metric("Servers Joined", server_count)

# Main application
def main():
    """Main application function"""
    init_database()
    init_session_state()
    load_css()
    
    # Create sample data if empty
    create_sample_data()
    
    if not st.session_state.authenticated:
        show_auth_page()
        return
    
    # Show main app
    show_sidebar()
    
    if st.session_state.page == 'servers':
        show_servers_page()
        show_create_server_modal()
        show_create_channel_modal()
        if 'show_forward_modal' in st.session_state and st.session_state.show_forward_modal:
            show_forward_modal()
    elif st.session_state.page == 'dm':
        show_dm_page()
        if 'show_forward_dm_modal' in st.session_state and st.session_state.show_forward_dm_modal:
            show_forward_dm_modal()
    elif st.session_state.page == 'profile':
        show_profile_page()

def create_sample_data():
    """Create sample data if database is empty"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Check if we have any users
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    
    if user_count == 0:
        # Create sample users
        sample_users = [
            ("admin", "admin@communicationx.com", "admin123", "Admin", "User"),
            ("alice", "alice@example.com", "password123", "Alice", "Smith"),
            ("bob", "bob@example.com", "password123", "Bob", "Johnson"),
        ]
        
        for username, email, password, first_name, last_name in sample_users:
            user_id = str(uuid.uuid4())
            password_hash = hash_password(password)
            cursor.execute("""
                INSERT INTO users (id, username, email, password_hash, first_name, last_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, email, password_hash, first_name, last_name))
        
        # Create sample server
        cursor.execute("""
            INSERT INTO servers (name, description, owner_id, is_public)
            VALUES (?, ?, ?, ?)
        """, ("General Community", "Welcome to the general community server!", 
              cursor.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0], True))
        
        server_id = cursor.lastrowid
        
        # Create sample channels
        channels = ["general", "random", "announcements"]
        for channel_name in channels:
            cursor.execute("""
                INSERT INTO channels (name, server_id)
                VALUES (?, ?)
            """, (channel_name, server_id))
        
        # Add all users to the server
        cursor.execute("SELECT id FROM users")
        all_user_ids = cursor.fetchall()
        
        for user_id_tuple in all_user_ids:
            cursor.execute("""
                INSERT INTO server_memberships (user_id, server_id)
                VALUES (?, ?)
            """, (user_id_tuple[0], server_id))
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()