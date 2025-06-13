#!/usr/bin/env python3
"""
Streamlit runner for CommunicationX
"""
import subprocess
import sys
import os

def main():
    """Run the Streamlit application"""
    # Change to the correct directory
    os.chdir('/home/runner/workspace')
    
    # Run streamlit
    cmd = [
        sys.executable, '-m', 'streamlit', 'run', 
        'streamlit_communicationx.py',
        '--server.port', '8501',
        '--server.address', '0.0.0.0',
        '--server.headless', 'true'
    ]
    
    subprocess.run(cmd)

if __name__ == '__main__':
    main()