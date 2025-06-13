import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import hashlib
import uuid
import base64
import logging
import json
import os
from sqlalchemy import create_engine, text, and_, or_, desc
from models import User, Server, Channel, Message, DirectMessage, ServerMembership, Call, CallMessage, Voicemail, Invitation, SharedFile, MessageReaction, MessageReport
from app import db, app
import streamlit_authenticator as stauth
from streamlit_option_menu import option_menu
from werkzeug.security import generate_password_hash, check_password_hash
from call_manager import call_manager, CallType, CallStatus

# Configure logging
logging.basicConfig(level=logging.INFO)

# Page configuration
st.set_page_config(
    page_title="CommunicationX",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database connection
@st.cache_resource
def init_database():
    """Initialize database connection"""
    with app.app_context():
        db.create_all()
        return True

# Initialize session state
def init_session_state():
    """Initialize Streamlit session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'current_user' not in st.session_state:
        st.session_state.current_user = None
    if 'current_server' not in st.session_state:
        st.session_state.current_server = None
    if 'current_channel' not in st.session_state:
        st.session_state.current_channel = None
    if 'dm_recipient' not in st.session_state:
        st.session_state.dm_recipient = None
    if 'refresh_messages' not in st.session_state:
        st.session_state.refresh_messages = 0
    if 'active_call' not in st.session_state:
        st.session_state.active_call = None

# Authentication functions
def authenticate_user(username, password):
    """Authenticate user with username/password"""
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            return user
        return None

def register_user(username, email, password, first_name="", last_name=""):
    """Register new user"""
    with app.app_context():
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            return None, "Username already exists"
        if User.query.filter_by(email=email).first():
            return None, "Email already exists"
        
        # Create new user
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            created_at=datetime.now()
        )
        db.session.add(user)
        
        # Auto-add to public servers
        public_servers = Server.query.filter_by(is_public=True).all()
        for server in public_servers:
            membership = ServerMembership(
                user_id=user.id,
                server_id=server.id,
                joined_at=datetime.now()
            )
            db.session.add(membership)
        
        db.session.commit()
        return user, "Success"

# Custom CSS styling
def load_custom_css():
    """Load custom CSS for Discord-like appearance"""
    st.markdown("""
    <style>
        /* Main app styling */
        .main {
            background-color: #36393f;
            color: #dcddde;
        }
        
        .sidebar .sidebar-content {
            background-color: #2f3136;
        }
        
        /* Message container styling */
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
        }
        
        .message-timestamp {
            font-size: 0.8em;
            color: #72767d;
            margin-left: 8px;
        }
        
        .message-content {
            margin-top: 4px;
            line-height: 1.4;
        }
        
        /* Server/Channel styling */
        .server-item, .channel-item {
            padding: 8px 12px;
            margin: 2px 0;
            border-radius: 4px;
            cursor: pointer;
            background-color: #40444b;
        }
        
        .server-item:hover, .channel-item:hover {
            background-color: #4f545c;
        }
        
        .active-server, .active-channel {
            background-color: #7289da !important;
            color: white !important;
        }
        
        /* Button styling */
        .stButton > button {
            background-color: #7289da;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
        }
        
        .stButton > button:hover {
            background-color: #677bc4;
        }
        
        /* Input styling */
        .stTextInput > div > div > input {
            background-color: #40444b;
            color: #dcddde;
            border: 1px solid #202225;
        }
        
        .stTextArea > div > div > textarea {
            background-color: #40444b;
            color: #dcddde;
            border: 1px solid #202225;
        }
        
        /* Call interface styling */
        .call-interface {
            background-color: #1e2124;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        
        .call-controls {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-top: 20px;
        }
        
        /* Online status indicators */
        .status-online { color: #43b581; }
        .status-away { color: #faa61a; }
        .status-busy { color: #f04747; }
        .status-invisible { color: #747f8d; }
        
        /* Reaction styling */
        .reaction {
            display: inline-block;
            background-color: #2f3136;
            border-radius: 12px;
            padding: 2px 6px;
            margin: 2px;
            font-size: 0.9em;
        }
        
        /* Notification styling */
        .notification {
            background-color: #7289da;
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            margin: 4px 0;
        }
        
        .notification-success { background-color: #43b581; }
        .notification-error { background-color: #f04747; }
        .notification-warning { background-color: #faa61a; }
    </style>
    """, unsafe_allow_html=True)

# Authentication page
def show_auth_page():
    """Display authentication (login/register) page"""
    st.title("🚀 CommunicationX")
    st.markdown("### Welcome to your communication platform")
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login to your account")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_submit = st.form_submit_button("Login", use_container_width=True)
            
            if login_submit:
                if username and password:
                    user = authenticate_user(username, password)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user_id = user.id
                        st.session_state.current_user = user
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
                else:
                    st.error("Please fill in all fields")
    
    with tab2:
        st.subheader("Create new account")
        with st.form("register_form"):
            new_username = st.text_input("Username*")
            new_email = st.text_input("Email*")
            new_first_name = st.text_input("First Name")
            new_last_name = st.text_input("Last Name")
            new_password = st.text_input("Password*", type="password")
            confirm_password = st.text_input("Confirm Password*", type="password")
            register_submit = st.form_submit_button("Register", use_container_width=True)
            
            if register_submit:
                if new_username and new_email and new_password and confirm_password:
                    if new_password != confirm_password:
                        st.error("Passwords do not match")
                    elif len(new_password) < 6:
                        st.error("Password must be at least 6 characters")
                    else:
                        user, message = register_user(new_username, new_email, new_password, new_first_name, new_last_name)
                        if user:
                            st.success("Registration successful! Please login.")
                        else:
                            st.error(message)
                else:
                    st.error("Please fill in all required fields")

# Sidebar navigation
def show_sidebar():
    """Display sidebar with servers and channels"""
    with st.sidebar:
        st.markdown(f"### Welcome, {st.session_state.current_user.username}!")
        
        # User status
        status_options = ["online", "away", "busy", "invisible"]
        current_status = st.selectbox("Status", status_options, 
                                    index=status_options.index(st.session_state.current_user.status))
        
        if current_status != st.session_state.current_user.status:
            with app.app_context():
                user = User.query.get(st.session_state.user_id)
                user.status = current_status
                db.session.commit()
                st.session_state.current_user.status = current_status
        
        st.markdown("---")
        
        # Navigation menu
        navigation = option_menu(
            "Navigation",
            ["Servers", "Direct Messages", "Voice Calls", "Profile", "Settings"],
            icons=["server", "chat-dots", "telephone", "person", "gear"],
            menu_icon="app-indicator",
            default_index=0,
        )
        
        if navigation == "Servers":
            show_servers_sidebar()
        elif navigation == "Direct Messages":
            show_dm_sidebar()
        elif navigation == "Voice Calls":
            show_calls_sidebar()
        elif navigation == "Profile":
            show_profile_sidebar()
        elif navigation == "Settings":
            show_settings_sidebar()
        
        st.markdown("---")
        
        # Logout button
        if st.button("Logout", use_container_width=True):
            for key in st.session_state.keys():
                del st.session_state[key]
            st.rerun()

def show_servers_sidebar():
    """Display servers in sidebar"""
    st.subheader("🏰 Servers")
    
    with app.app_context():
        # Get user's servers
        user_servers = db.session.query(Server).join(ServerMembership).filter(
            ServerMembership.user_id == st.session_state.user_id
        ).all()
        
        for server in user_servers:
            server_key = f"server_{server.id}"
            if st.button(f"📋 {server.name}", key=server_key, use_container_width=True):
                st.session_state.current_server = server.id
                st.session_state.current_channel = None
                st.session_state.dm_recipient = None
        
        # Show channels for selected server
        if st.session_state.current_server:
            st.markdown("#### Channels")
            channels = Channel.query.filter_by(server_id=st.session_state.current_server).all()
            
            for channel in channels:
                channel_key = f"channel_{channel.id}"
                if st.button(f"# {channel.name}", key=channel_key, use_container_width=True):
                    st.session_state.current_channel = channel.id
                    st.session_state.dm_recipient = None
        
        # Create server button
        if st.button("➕ Create Server", use_container_width=True):
            st.session_state.show_create_server = True

def show_dm_sidebar():
    """Display direct messages in sidebar"""
    st.subheader("💬 Direct Messages")
    
    with app.app_context():
        # Get recent DM conversations
        dm_query = db.session.query(DirectMessage).filter(
            or_(
                DirectMessage.sender_id == st.session_state.user_id,
                DirectMessage.recipient_id == st.session_state.user_id
            )
        ).order_by(desc(DirectMessage.created_at)).limit(50)
        
        conversations = {}
        for dm in dm_query:
            other_user_id = dm.recipient_id if dm.sender_id == st.session_state.user_id else dm.sender_id
            if other_user_id not in conversations:
                other_user = User.query.get(other_user_id)
                conversations[other_user_id] = {
                    'user': other_user,
                    'last_message': dm,
                    'unread_count': 0
                }
        
        # Display conversations
        for user_id, conv in conversations.items():
            user = conv['user']
            status_icon = {"online": "🟢", "away": "🟡", "busy": "🔴", "invisible": "⚫"}.get(user.status, "⚫")
            
            if st.button(f"{status_icon} {user.username}", key=f"dm_{user_id}", use_container_width=True):
                st.session_state.dm_recipient = user_id
                st.session_state.current_server = None
                st.session_state.current_channel = None
        
        # Start new DM
        if st.button("➕ New Message", use_container_width=True):
            st.session_state.show_new_dm = True

def show_calls_sidebar():
    """Display voice calls in sidebar"""
    st.subheader("📞 Voice Calls")
    
    # Active call status
    if st.session_state.active_call:
        st.info("🔊 In active call")
        if st.button("End Call", type="primary", use_container_width=True):
            call_manager.end_call(st.session_state.active_call)
            st.session_state.active_call = None
            st.rerun()
    
    with app.app_context():
        # Recent calls
        recent_calls = Call.query.filter(
            or_(
                Call.caller_id == st.session_state.user_id,
                Call.recipient_id == st.session_state.user_id
            )
        ).order_by(desc(Call.started_at)).limit(10).all()
        
        st.markdown("#### Recent Calls")
        for call in recent_calls:
            other_user_id = call.recipient_id if call.caller_id == st.session_state.user_id else call.caller_id
            other_user = User.query.get(other_user_id)
            
            call_icon = "📞" if call.call_type == "audio" else "📹"
            status_icon = {"pending": "⏳", "active": "🟢", "ended": "🔴", "declined": "❌", "missed": "⚪"}.get(call.status, "❓")
            
            st.text(f"{call_icon} {status_icon} {other_user.username}")
        
        # Voicemails
        voicemails = Voicemail.query.filter_by(
            recipient_id=st.session_state.user_id,
            is_read=False
        ).count()
        
        if voicemails > 0:
            st.info(f"📧 {voicemails} new voicemail(s)")

def show_profile_sidebar():
    """Display profile information in sidebar"""
    st.subheader("👤 Profile")
    user = st.session_state.current_user
    
    st.text(f"Username: {user.username}")
    st.text(f"Email: {user.email}")
    if user.first_name:
        st.text(f"Name: {user.first_name} {user.last_name or ''}")
    
    if st.button("Edit Profile", use_container_width=True):
        st.session_state.show_edit_profile = True

def show_settings_sidebar():
    """Display settings in sidebar"""
    st.subheader("⚙️ Settings")
    
    # Notification settings
    st.checkbox("Desktop Notifications", value=True)
    st.checkbox("Sound Notifications", value=True)
    st.checkbox("Email Notifications", value=False)
    
    # Theme settings
    st.selectbox("Theme", ["Dark", "Light"], index=0)
    
    # Privacy settings
    st.checkbox("Show Online Status", value=True)
    st.checkbox("Allow Direct Messages", value=True)

# Main content area functions
def show_channel_messages():
    """Display messages for current channel"""
    if not st.session_state.current_channel:
        st.info("Select a channel to view messages")
        return
    
    with app.app_context():
        channel = Channel.query.get(st.session_state.current_channel)
        server = Server.query.get(st.session_state.current_server)
        
        st.header(f"# {channel.name}")
        st.caption(f"Server: {server.name}")
        
        # Message input
        with st.form("send_message", clear_on_submit=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                message_content = st.text_area("Type your message...", height=60, key="channel_message")
            with col2:
                st.write("")  # Spacing
                send_button = st.form_submit_button("Send", use_container_width=True)
                
            if send_button and message_content.strip():
                # Save message to database
                new_message = Message(
                    content=message_content.strip(),
                    author_id=st.session_state.user_id,
                    channel_id=st.session_state.current_channel,
                    created_at=datetime.now()
                )
                db.session.add(new_message)
                db.session.commit()
                st.session_state.refresh_messages += 1
                st.rerun()
        
        # Display messages
        messages = Message.query.filter_by(
            channel_id=st.session_state.current_channel
        ).order_by(desc(Message.created_at)).limit(50).all()
        
        st.markdown("---")
        
        for message in reversed(messages):
            author = User.query.get(message.author_id)
            display_message(message, author)

def show_direct_messages():
    """Display direct messages with selected user"""
    if not st.session_state.dm_recipient:
        st.info("Select a conversation to view messages")
        return
    
    with app.app_context():
        recipient = User.query.get(st.session_state.dm_recipient)
        
        st.header(f"💬 {recipient.username}")
        status_icon = {"online": "🟢", "away": "🟡", "busy": "🔴", "invisible": "⚫"}.get(recipient.status, "⚫")
        st.caption(f"Status: {status_icon} {recipient.status.title()}")
        
        # Message input
        with st.form("send_dm", clear_on_submit=True):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                dm_content = st.text_area("Type your message...", height=60, key="dm_message")
            with col2:
                st.write("")  # Spacing
                send_button = st.form_submit_button("Send", use_container_width=True)
            with col3:
                st.write("")  # Spacing
                call_button = st.form_submit_button("📞 Call", use_container_width=True)
                
            if send_button and dm_content.strip():
                # Save DM to database
                new_dm = DirectMessage(
                    content=dm_content.strip(),
                    sender_id=st.session_state.user_id,
                    recipient_id=st.session_state.dm_recipient,
                    created_at=datetime.now()
                )
                db.session.add(new_dm)
                db.session.commit()
                st.session_state.refresh_messages += 1
                st.rerun()
            
            if call_button:
                # Initiate call
                call_id = call_manager.create_call(
                    st.session_state.user_id,
                    st.session_state.dm_recipient,
                    CallType.AUDIO
                )
                st.session_state.active_call = call_id
                st.success(f"Calling {recipient.username}...")
                st.rerun()
        
        # Display DMs
        dms = DirectMessage.query.filter(
            and_(
                or_(
                    and_(DirectMessage.sender_id == st.session_state.user_id, 
                         DirectMessage.recipient_id == st.session_state.dm_recipient),
                    and_(DirectMessage.sender_id == st.session_state.dm_recipient, 
                         DirectMessage.recipient_id == st.session_state.user_id)
                )
            )
        ).order_by(desc(DirectMessage.created_at)).limit(50).all()
        
        st.markdown("---")
        
        for dm in reversed(dms):
            author = User.query.get(dm.sender_id)
            display_dm(dm, author)

def display_message(message, author):
    """Display a single message with reactions and actions"""
    timestamp = message.created_at.strftime("%H:%M")
    
    with st.container():
        col1, col2 = st.columns([1, 6])
        
        with col1:
            status_icon = {"online": "🟢", "away": "🟡", "busy": "🔴", "invisible": "⚫"}.get(author.status, "⚫")
            st.markdown(f"**{status_icon} {author.username}**")
            st.caption(timestamp)
        
        with col2:
            st.markdown(f"<div class='message-content'>{message.content}</div>", unsafe_allow_html=True)
            
            # Message actions
            col_react, col_reply, col_delete = st.columns([1, 1, 1])
            
            with col_react:
                if st.button("👍", key=f"react_{message.id}"):
                    add_reaction(message.id, "👍")
            
            with col_reply:
                if st.button("↩️", key=f"reply_{message.id}"):
                    st.session_state.reply_to = message.id
            
            if message.author_id == st.session_state.user_id:
                with col_delete:
                    if st.button("🗑️", key=f"delete_{message.id}"):
                        delete_message(message.id)
            
            # Display reactions
            reactions = MessageReaction.query.filter_by(message_id=message.id).all()
            if reactions:
                reaction_counts = {}
                for reaction in reactions:
                    emoji = reaction.emoji
                    if emoji in reaction_counts:
                        reaction_counts[emoji] += 1
                    else:
                        reaction_counts[emoji] = 1
                
                reaction_text = " ".join([f"{emoji} {count}" for emoji, count in reaction_counts.items()])
                st.markdown(f"<div class='reaction'>{reaction_text}</div>", unsafe_allow_html=True)
        
        st.markdown("---")

def display_dm(dm, author):
    """Display a single direct message"""
    timestamp = dm.created_at.strftime("%H:%M")
    
    with st.container():
        col1, col2 = st.columns([1, 6])
        
        with col1:
            status_icon = {"online": "🟢", "away": "🟡", "busy": "🔴", "invisible": "⚫"}.get(author.status, "⚫")
            st.markdown(f"**{status_icon} {author.username}**")
            st.caption(timestamp)
        
        with col2:
            st.markdown(f"<div class='message-content'>{dm.content}</div>", unsafe_allow_html=True)
        
        st.markdown("---")

def add_reaction(message_id, emoji):
    """Add reaction to message"""
    with app.app_context():
        # Check if user already reacted with this emoji
        existing = MessageReaction.query.filter_by(
            message_id=message_id,
            user_id=st.session_state.user_id,
            emoji=emoji
        ).first()
        
        if existing:
            db.session.delete(existing)
        else:
            reaction = MessageReaction(
                message_id=message_id,
                user_id=st.session_state.user_id,
                emoji=emoji,
                created_at=datetime.now()
            )
            db.session.add(reaction)
        
        db.session.commit()
        st.rerun()

def delete_message(message_id):
    """Delete message"""
    with app.app_context():
        message = Message.query.get(message_id)
        if message and message.author_id == st.session_state.user_id:
            db.session.delete(message)
            db.session.commit()
            st.rerun()

# Modal dialogs
def show_create_server_modal():
    """Show create server dialog"""
    if 'show_create_server' in st.session_state and st.session_state.show_create_server:
        with st.expander("Create New Server", expanded=True):
            with st.form("create_server_form"):
                server_name = st.text_input("Server Name*")
                server_description = st.text_area("Description")
                is_public = st.checkbox("Public Server", value=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    create_button = st.form_submit_button("Create Server", use_container_width=True)
                with col2:
                    cancel_button = st.form_submit_button("Cancel", use_container_width=True)
                
                if create_button and server_name:
                    with app.app_context():
                        new_server = Server(
                            name=server_name,
                            description=server_description,
                            owner_id=st.session_state.user_id,
                            is_public=is_public,
                            created_at=datetime.now()
                        )
                        db.session.add(new_server)
                        db.session.flush()
                        
                        # Create default channel
                        default_channel = Channel(
                            name="general",
                            server_id=new_server.id,
                            created_at=datetime.now()
                        )
                        db.session.add(default_channel)
                        
                        # Add creator as member
                        membership = ServerMembership(
                            user_id=st.session_state.user_id,
                            server_id=new_server.id,
                            joined_at=datetime.now()
                        )
                        db.session.add(membership)
                        
                        db.session.commit()
                        
                        st.success(f"Server '{server_name}' created successfully!")
                        del st.session_state.show_create_server
                        st.rerun()
                
                if cancel_button:
                    del st.session_state.show_create_server
                    st.rerun()

def show_call_interface():
    """Show active call interface"""
    if st.session_state.active_call:
        st.markdown("### 📞 Active Call")
        
        with app.app_context():
            call = call_manager.get_call(st.session_state.active_call)
            if call:
                other_user_id = call.recipient_id if call.caller_id == st.session_state.user_id else call.caller_id
                other_user = User.query.get(other_user_id)
                
                st.markdown(f"**Connected with: {other_user.username}**")
                st.markdown(f"**Call Type:** {'📞 Audio' if call.call_type == CallType.AUDIO else '📹 Video'}")
                st.markdown(f"**Status:** {call.status.value.title()}")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("🔇 Mute", key="mute_call"):
                        st.info("Microphone muted")
                
                with col2:
                    if call.call_type == CallType.VIDEO:
                        if st.button("📹 Video Off", key="video_off"):
                            st.info("Video disabled")
                
                with col3:
                    if st.button("📞 End Call", key="end_call", type="primary"):
                        call_manager.end_call(st.session_state.active_call)
                        st.session_state.active_call = None
                        st.success("Call ended")
                        st.rerun()

# Main application
def main():
    """Main application function"""
    init_database()
    init_session_state()
    load_custom_css()
    
    if not st.session_state.authenticated:
        show_auth_page()
        return
    
    # Show sidebar
    show_sidebar()
    
    # Main content area
    if st.session_state.current_channel:
        show_channel_messages()
    elif st.session_state.dm_recipient:
        show_direct_messages()
    else:
        st.title("🚀 Welcome to CommunicationX")
        st.markdown("""
        ### Your complete communication platform
        
        **Features:**
        - 🏰 Server-based messaging with channels
        - 💬 Direct messaging with online status
        - 📞 Voice and video calling
        - 📧 Voicemail system
        - 👥 User management and profiles
        - 🎭 Message reactions and interactions
        - 📱 Real-time notifications
        
        **Getting Started:**
        1. Browse servers in the sidebar
        2. Join channels to participate in conversations
        3. Start direct messages with other users
        4. Make voice/video calls
        5. Customize your profile and settings
        
        Select a server channel or start a direct message to begin chatting!
        """)
        
        # Show active call interface if in call
        show_call_interface()
        
        # Show recent activity
        with app.app_context():
            st.markdown("### 📈 Recent Activity")
            
            # Recent messages across all servers
            recent_messages = db.session.query(Message).join(Channel).join(Server).join(ServerMembership).filter(
                ServerMembership.user_id == st.session_state.user_id
            ).order_by(desc(Message.created_at)).limit(5).all()
            
            if recent_messages:
                for msg in recent_messages:
                    author = User.query.get(msg.author_id)
                    channel = Channel.query.get(msg.channel_id)
                    server = Server.query.get(channel.server_id)
                    
                    st.markdown(f"**{author.username}** in #{channel.name} ({server.name}): {msg.content[:100]}...")
            else:
                st.info("No recent activity. Join a server or start a conversation!")
    
    # Show modals
    show_create_server_modal()
    
    # Auto-refresh for real-time updates
    time.sleep(1)
    if st.session_state.current_channel or st.session_state.dm_recipient:
        st.rerun()

if __name__ == "__main__":
    main()