from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, make_response
from flask_login import login_required, current_user
from app import db
from models import CodeWorkspace, CodeFile, WorkspaceCollaborator, DesignWorkspace, DesignProject, DesignCollaborator, BrowserSession, BrowserParticipant, ToolFile, Server, User
import uuid
import json
from datetime import datetime

tools = Blueprint('tools', __name__)

# HackKit Routes
@tools.route('/hackkit/<workspace_type>')
@login_required
def hackkit(workspace_type):
    """HackKit code editor interface"""
    if workspace_type not in ['personal', 'group']:
        return redirect(url_for('home'))
    
    workspaces = CodeWorkspace.query.filter_by(
        owner_id=current_user.id,
        workspace_type=workspace_type
    ).order_by(CodeWorkspace.updated_at.desc()).all()
    
    # Get user's servers for group workspaces
    servers = []
    if workspace_type == 'group':
        servers = Server.query.filter_by(owner_id=current_user.id).all()
    
    return render_template('tools/hackkit.html', 
                         workspace_type=workspace_type, 
                         workspaces=workspaces,
                         servers=servers)

@tools.route('/hackkit/create', methods=['POST'])
@login_required
def create_code_workspace():
    """Create new code workspace"""
    data = request.get_json()
    
    workspace = CodeWorkspace(
        name=data.get('name', 'New Workspace'),
        description=data.get('description', ''),
        workspace_type=data.get('type', 'personal'),
        owner_id=current_user.id,
        server_id=data.get('server_id') if data.get('type') == 'group' else None,
        language=data.get('language', 'javascript')
    )
    
    db.session.add(workspace)
    db.session.commit()
    
    # Create initial file
    initial_file = CodeFile(
        workspace_id=workspace.id,
        filename='main.' + {'javascript': 'js', 'python': 'py', 'java': 'java', 'cpp': 'cpp'}.get(workspace.language, 'txt'),
        file_path='/main.' + {'javascript': 'js', 'python': 'py', 'java': 'java', 'cpp': 'cpp'}.get(workspace.language, 'txt'),
        content=get_initial_code(workspace.language),
        language=workspace.language,
        created_by=current_user.id
    )
    
    db.session.add(initial_file)
    db.session.commit()
    
    return jsonify({'success': True, 'workspace_id': workspace.id})

@tools.route('/hackkit/workspace/<int:workspace_id>')
@login_required
def code_workspace(workspace_id):
    """Individual workspace interface"""
    workspace = CodeWorkspace.query.get_or_404(workspace_id)
    
    # Check permissions
    if workspace.owner_id != current_user.id:
        collaborator = WorkspaceCollaborator.query.filter_by(
            workspace_id=workspace_id,
            user_id=current_user.id
        ).first()
        if not collaborator:
            return redirect(url_for('home'))
    
    files = CodeFile.query.filter_by(workspace_id=workspace_id).order_by(CodeFile.filename).all()
    collaborators = WorkspaceCollaborator.query.filter_by(workspace_id=workspace_id).all()
    
    return render_template('tools/code_editor.html', 
                         workspace=workspace, 
                         files=files,
                         collaborators=collaborators)

# Canva Routes
@tools.route('/canva/<workspace_type>')
@login_required
def canva(workspace_type):
    """Canva design tool interface"""
    if workspace_type not in ['personal', 'group']:
        return redirect(url_for('home'))
    
    workspaces = DesignWorkspace.query.filter_by(
        owner_id=current_user.id,
        workspace_type=workspace_type
    ).order_by(DesignWorkspace.updated_at.desc()).all()
    
    servers = []
    if workspace_type == 'group':
        servers = Server.query.filter_by(owner_id=current_user.id).all()
    
    return render_template('tools/canva.html', 
                         workspace_type=workspace_type, 
                         workspaces=workspaces,
                         servers=servers)

@tools.route('/canva/create', methods=['POST'])
@login_required
def create_design_workspace():
    """Create new design workspace"""
    data = request.get_json()
    
    workspace = DesignWorkspace(
        name=data.get('name', 'New Design'),
        description=data.get('description', ''),
        workspace_type=data.get('type', 'personal'),
        owner_id=current_user.id,
        server_id=data.get('server_id') if data.get('type') == 'group' else None,
        template_type=data.get('template_type', 'custom')
    )
    
    db.session.add(workspace)
    db.session.commit()
    
    # Create initial project
    initial_project = DesignProject(
        workspace_id=workspace.id,
        name='Untitled Design',
        canvas_data=json.dumps(get_initial_canvas()),
        created_by=current_user.id
    )
    
    db.session.add(initial_project)
    db.session.commit()
    
    return jsonify({'success': True, 'workspace_id': workspace.id})

@tools.route('/canva/workspace/<int:workspace_id>')
@login_required
def design_workspace(workspace_id):
    """Individual design workspace"""
    workspace = DesignWorkspace.query.get_or_404(workspace_id)
    
    # Check permissions
    if workspace.owner_id != current_user.id:
        collaborator = DesignCollaborator.query.filter_by(
            workspace_id=workspace_id,
            user_id=current_user.id
        ).first()
        if not collaborator:
            return redirect(url_for('home'))
    
    projects = DesignProject.query.filter_by(workspace_id=workspace_id).order_by(DesignProject.updated_at.desc()).all()
    collaborators = DesignCollaborator.query.filter_by(workspace_id=workspace_id).all()
    
    return render_template('tools/design_editor.html', 
                         workspace=workspace, 
                         projects=projects,
                         collaborators=collaborators)

# Opera Browser Routes
@tools.route('/opera/<session_type>')
@login_required
def opera(session_type):
    """Opera browser interface"""
    if session_type not in ['personal', 'group']:
        return redirect(url_for('home'))
    
    sessions = BrowserSession.query.filter_by(
        owner_id=current_user.id,
        session_type=session_type,
        is_active=True
    ).order_by(BrowserSession.updated_at.desc()).all()
    
    servers = []
    if session_type == 'group':
        servers = Server.query.filter_by(owner_id=current_user.id).all()
    
    return render_template('tools/opera.html', 
                         session_type=session_type, 
                         sessions=sessions,
                         servers=servers)

@tools.route('/opera/create', methods=['POST'])
@login_required
def create_browser_session():
    """Create new browser session"""
    data = request.get_json()
    
    session_obj = BrowserSession(
        session_name=data.get('name', 'New Session'),
        url=data.get('url', 'https://www.google.com'),
        session_type=data.get('type', 'personal'),
        owner_id=current_user.id,
        server_id=data.get('server_id') if data.get('type') == 'group' else None
    )
    
    db.session.add(session_obj)
    db.session.commit()
    
    return jsonify({'success': True, 'session_id': session_obj.id})

@tools.route('/opera/session/<int:session_id>')
@login_required
def browser_session(session_id):
    """Individual browser session"""
    browser_session = BrowserSession.query.get_or_404(session_id)
    
    # Check permissions
    if browser_session.owner_id != current_user.id:
        participant = BrowserParticipant.query.filter_by(
            session_id=session_id,
            user_id=current_user.id
        ).first()
        if not participant:
            return redirect(url_for('home'))
    
    participants = BrowserParticipant.query.filter_by(session_id=session_id).all()
    
    return render_template('tools/browser.html', 
                         session=browser_session,
                         participants=participants)

# Files Manager Route
@tools.route('/files')
@login_required
def files_manager():
    """Files manager interface"""
    code_files = ToolFile.query.filter_by(owner_id=current_user.id, file_type='code').all()
    design_files = ToolFile.query.filter_by(owner_id=current_user.id, file_type='design').all()
    browser_files = ToolFile.query.filter_by(owner_id=current_user.id, file_type='browser').all()
    
    return render_template('tools/files.html', 
                         code_files=code_files,
                         design_files=design_files,
                         browser_files=browser_files)

# API Routes for file operations
@tools.route('/api/files/upload', methods=['POST'])
@login_required
def upload_file():
    """Upload file to tools storage"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    file_type = request.form.get('file_type', 'code')
    workspace_id = request.form.get('workspace_id')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    file_data = file.read()
    
    tool_file = ToolFile(
        filename=file.filename,
        file_path=f"/{file_type}/{file.filename}",
        file_type=file_type,
        workspace_id=int(workspace_id) if workspace_id else None,
        file_data=file_data,
        file_size=len(file_data),
        mime_type=file.content_type,
        owner_id=current_user.id
    )
    
    db.session.add(tool_file)
    db.session.commit()
    
    return jsonify({'success': True, 'file_id': tool_file.id})

@tools.route('/api/files/<int:file_id>/download')
@login_required
def download_file(file_id):
    """Download file from tools storage"""
    tool_file = ToolFile.query.get_or_404(file_id)
    
    if tool_file.owner_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    from flask import Response
    return Response(
        tool_file.file_data,
        mimetype=tool_file.mime_type,
        headers={"Content-Disposition": f"attachment;filename={tool_file.filename}"}
    )

def get_initial_code(language):
    """Get initial code template for language"""
    templates = {
        'javascript': '''// Welcome to HackKit!
console.log("Hello, World!");

function greet(name) {
    return `Hello, ${name}!`;
}

greet("Developer");''',
        'python': '''# Welcome to HackKit!
print("Hello, World!")

def greet(name):
    return f"Hello, {name}!"

greet("Developer")''',
        'java': '''// Welcome to HackKit!
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
    
    public static String greet(String name) {
        return "Hello, " + name + "!";
    }
}''',
        'cpp': '''// Welcome to HackKit!
#include <iostream>
#include <string>

int main() {
    std::cout << "Hello, World!" << std::endl;
    return 0;
}

std::string greet(const std::string& name) {
    return "Hello, " + name + "!";
}'''
    }
    return templates.get(language, '// Welcome to HackKit!')

# Opera Browser Proxy Route
@tools.route('/opera/proxy')
def opera_proxy():
    """Proxy for loading external websites"""
    url = request.args.get('url')
    if not url:
        return "No URL provided", 400
    
    try:
        import requests
        from urllib.parse import urljoin, urlparse
        
        # Add headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        
        # Modify content to work better in iframe
        content = response.text
        if 'text/html' in response.headers.get('content-type', ''):
            # Add base tag to fix relative URLs
            base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            content = content.replace('<head>', f'<head><base href="{base_url}">')
            
            # Remove X-Frame-Options headers in the HTML
            content = content.replace('X-Frame-Options', 'X-Frame-Options-Disabled')
        
        # Create response with modified headers
        resp = make_response(content)
        
        # Copy safe headers
        safe_headers = ['content-type', 'content-length']
        for header in safe_headers:
            if header in response.headers:
                resp.headers[header] = response.headers[header]
        
        # Remove headers that block iframe embedding
        resp.headers.pop('X-Frame-Options', None)
        resp.headers.pop('Content-Security-Policy', None)
        
        return resp
        
    except Exception as e:
        error_html = f"""
        <html>
        <body style="font-family: Arial; padding: 20px; background: #f5f5f5;">
            <div style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h3 style="color: #d73527;">Unable to Load Website</h3>
                <p>The website <strong>{url}</strong> cannot be loaded in the browser.</p>
                <p><strong>Reason:</strong> {str(e)}</p>
                <p><a href="{url}" target="_blank" style="color: #0066cc;">Open in New Tab</a></p>
            </div>
        </body>
        </html>
        """
        return error_html, 200

def get_initial_canvas():
    """Get initial canvas data for design projects"""
    return {
        "version": "1.0",
        "width": 800,
        "height": 600,
        "background": "#ffffff",
        "objects": [
            {
                "type": "text",
                "text": "Welcome to Canva!",
                "x": 100,
                "y": 100,
                "fontSize": 24,
                "fontFamily": "Arial",
                "fill": "#333333"
            }
        ]
    }