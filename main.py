from app import app, socketio
import routes  # noqa: F401
import socket_events  # noqa: F401

# Register advanced Discord-like features
from advanced_routes import advanced
app.register_blueprint(advanced, url_prefix='/api/advanced')

# Register tools (HackKit, Canva, Opera, Files)
try:
    from tools_routes import tools
    app.register_blueprint(tools, url_prefix='/tools')
    print("Tools routes registered successfully")
except Exception as e:
    print(f"Error registering tools routes: {e}")

# For Gunicorn compatibility
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)