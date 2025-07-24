#!/usr/bin/env python3

import os
import time
import threading
import subprocess
import platform
import shutil
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

from project_database import db
from environment_detector import EnvironmentDetector
from logger import logger

class LaunchAPIServer:
    def __init__(self, port=7871, launcher=None):
        self.app = Flask(__name__)
        CORS(self.app)  # Allow cross-origin requests from Gradio
        self.port = port
        self.launcher = launcher
        self.env_detector = EnvironmentDetector()
        self.setup_routes()
        
    def setup_routes(self):
        """Setup API routes"""
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Health check endpoint"""
            return jsonify({"status": "healthy", "timestamp": time.time()})
        
        @self.app.route('/launch', methods=['GET', 'POST'])
        def launch_project():
            """Launch a project via API using project ID"""
            import time
            request_time = time.strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"\n🌐 [API] ==========================================")
            print(f"🌐 [API] 🚀 LAUNCH REQUEST RECEIVED")
            print(f"🌐 [API] Time: {request_time}")
            print(f"🌐 [API] Method: {request.method}")
            print(f"🌐 [API] ==========================================")
            
            try:
                print(f"🌐 [API] Request URL: {request.url}")
                print(f"🌐 [API] Request args: {dict(request.args)}")
                
                # Get project_id from query parameter (for GET requests)
                project_id = request.args.get('project_id')
                
                if not project_id:
                    print(f"🌐 [API] ❌ ERROR: No project_id provided!")
                    return jsonify({"success": False, "error": "Missing project_id parameter"}), 400
                
                try:
                    project_index = int(project_id)
                    print(f"🌐 [API] ✅ Project ID: {project_index}")
                except ValueError:
                    print(f"🌐 [API] ❌ ERROR: Invalid project_id format: {project_id}")
                    return jsonify({"success": False, "error": "Invalid project_id format"}), 400
                
                # Get project data from launcher's current projects
                print(f"🌐 [API] Looking up project by index {project_index}...")
                if project_index < 0 or project_index >= len(self.launcher.current_projects):
                    print(f"🌐 [API] ❌ ERROR: Project index {project_index} out of range (0-{len(self.launcher.current_projects)-1})")
                    return jsonify({"success": False, "error": f"Project index {project_index} out of range"}), 400
                
                project = self.launcher.current_projects[project_index]
                project_name = project.get('name', 'Unknown')
                project_path = project.get('path', '')
                
                print(f"🌐 [API] ✅ Found project: {project_name} at {project_path}")
                
                print(f"\n🚀 [LAUNCH BUTTON CLICKED] ====================================")
                print(f"🚀 [TERMINAL] APP CARD DETAILS:")
                print(f"🚀 [TERMINAL]   Project ID: {project_index}")
                print(f"🚀 [TERMINAL]   Project Name: {project_name}")
                print(f"🚀 [TERMINAL]   Project Path: {project_path}")
                print(f"🚀 [TERMINAL]   API Request Time: {request_time}")
                
                if not project_name or not project_path:
                    print(f"🚀 [TERMINAL] ❌ ERROR: Missing project name or path!")
                    print(f"🚀 [TERMINAL]   Name: '{project_name}' (length: {len(project_name)})")
                    print(f"🚀 [TERMINAL]   Path: '{project_path}' (length: {len(project_path)})")
                    print(f"🚀 [LAUNCH BUTTON CLICKED] ====================================\n")
                    return jsonify({"success": False, "error": "Missing project name or path"}), 400
                
                # Try to get additional project info from database if available
                try:
                    import sys
                    sys.path.append('.')
                    from project_database import ProjectDatabase
                    db = ProjectDatabase()
                    project_data = db.get_project_by_path(project_path)
                    if project_data:
                        env_type = project_data.get('environment_type', 'Unknown')
                        description = project_data.get('description', 'No description')
                        main_script = project_data.get('main_script', 'Unknown')
                        print(f"🚀 [TERMINAL]   Environment: {env_type}")
                        print(f"🚀 [TERMINAL]   Main Script: {main_script}")
                        print(f"🚀 [TERMINAL]   Description: {description[:100]}...")
                    else:
                        print(f"🚀 [TERMINAL]   Additional project info not available in database")
                except Exception as e:
                    print(f"🚀 [TERMINAL]   Could not load additional project info: {e}")
                
                print(f"🚀 [LAUNCH BUTTON CLICKED] ====================================\n")
                
                logger.info(f"🌐 API launch request: {project_name} at {project_path}")
                print(f"🌐 [API] ✅ Validation passed - proceeding with launch")
                
                print(f"🌐 [API] Starting background launch thread...")
                
                # Execute the launch in a background thread
                def launch_in_background():
                    try:
                        print(f"🌐 [API] Background thread started for {project_name}")
                        result = self.execute_launch(project_path, project_name, 0)
                        print(f"🌐 [API] Background launch completed: {result}")
                        logger.info(f"API launch completed: {result}")
                    except Exception as e:
                        print(f"🌐 [API] Background launch FAILED: {str(e)}")
                        logger.error(f"API launch failed: {str(e)}")
                
                thread = threading.Thread(target=launch_in_background, daemon=True)
                thread.start()
                print(f"🌐 [API] Background thread started successfully")
                
                response_data = {
                    "success": True,
                    "message": f"Launch initiated for {project_name}",
                    "project_id": project_index,
                    "project_name": project_name,
                    "request_time": request_time
                }
                print(f"🌐 [API] ✅ Sending success response: {response_data}")
                logger.info(f"🌐 API response sent: {response_data}")
                
                return jsonify(response_data)
                
            except Exception as e:
                error_msg = str(e)
                print(f"🌐 [API] EXCEPTION in launch_project: {error_msg}")
                print(f"🌐 [API] Exception type: {type(e)}")
                import traceback
                print(f"🌐 [API] Traceback: {traceback.format_exc()}")
                logger.error(f"API launch error: {error_msg}")
                return jsonify({
                    "success": False,
                    "error": error_msg
                }), 500
        
        @self.app.route('/test', methods=['GET', 'POST'])
        def test_endpoint():
            """Simple test endpoint to verify API is working"""
            print(f"🌐 [API] TEST endpoint accessed")
            print(f"🌐 [API] Method: {request.method}")
            return jsonify({
                "status": "API server is working",
                "timestamp": time.time(),
                "method": request.method
            })
    
    def open_terminal(self, command):
        """Opens a new terminal window and executes the given command - cross-platform"""
        os_name = platform.system()
        print(f"🌐 [API] Opening terminal on {os_name} with command: {command[:100]}...")
        logger.info(f"Opening terminal on {os_name}")
        
        try:
            if os_name == "Windows":
                # Opens a new cmd window, runs the command, and keeps it open (/k)
                subprocess.Popen(['cmd', '/c', 'start', 'cmd.exe', '/k', command])
            elif os_name == "Linux":
                # Try different terminal emulators in order of preference
                terminals_to_try = [
                    'gnome-terminal',
                    'konsole', 
                    'xfce4-terminal',
                    'mate-terminal',
                    'lxterminal',
                    'terminator',
                    'xterm'
                ]
                
                terminal_found = None
                for terminal in terminals_to_try:
                    if shutil.which(terminal):
                        terminal_found = terminal
                        print(f"🌐 [API] Found terminal: {terminal}")
                        break
                
                if not terminal_found:
                    raise OSError("No suitable terminal emulator found. Please install gnome-terminal, konsole, or xterm.")
                
                # Execute command based on terminal type
                if terminal_found == 'gnome-terminal':
                    subprocess.Popen([terminal_found, '--', 'bash', '-c', f'{command}; exec bash'])
                elif terminal_found == 'konsole':
                    subprocess.Popen([terminal_found, '-e', 'bash', '-c', f'{command}; exec bash'])
                elif terminal_found in ['xfce4-terminal', 'mate-terminal', 'lxterminal']:
                    subprocess.Popen([terminal_found, '-e', f'bash -c "{command}; exec bash"'])
                elif terminal_found == 'terminator':
                    subprocess.Popen([terminal_found, '-x', 'bash', '-c', f'{command}; exec bash'])
                elif terminal_found == 'xterm':
                    subprocess.Popen([terminal_found, '-e', f'bash -c "{command}; exec bash"'])
                else:
                    # Fallback for any other terminal
                    subprocess.Popen([terminal_found, '-e', f'bash -c "{command}; exec bash"'])
                    
            elif os_name == "Darwin":  # macOS
                # Uses AppleScript to open Terminal.app and run the command
                subprocess.Popen(['osascript', '-e', f'tell application "Terminal" to do script "{command}"'])
            else:
                raise OSError(f"Unsupported operating system: {os_name}")
                
            print(f"🌐 [API] Terminal opened successfully")
            logger.info("Terminal opened successfully")
            return "Terminal launched successfully!"
            
        except Exception as e:
            error_msg = f"Error launching terminal: {str(e)}"
            print(f"🌐 [API] ERROR: {error_msg}")
            logger.error(error_msg)
            return error_msg
    
    def execute_launch(self, project_path: str, project_name: str, launch_id: int = 0) -> str:
        """Execute the project launch using AI-generated launch command"""
        print(f"🌐 [API] ===== AI-POWERED LAUNCH =====")
        print(f"🌐 [API] Project: {project_name}")
        print(f"🌐 [API] Path: {project_path}")
        
        try:
            print(f"🌐 [API] Step 1: Getting project from database...")
            # Get project data from database to access AI-generated launch command
            project_data = db.get_project_by_path(project_path)
            
            if not project_data:
                print(f"🌐 [API] Project not found in database, using fallback...")
                return self._fallback_launch(project_path, project_name)
            
            # Get AI-generated launch information
            launch_command = project_data.get('launch_command')
            launch_type = project_data.get('launch_type', 'unknown')
            working_dir = project_data.get('launch_working_directory', '.')
            launch_args = project_data.get('launch_args', '')
            confidence = project_data.get('launch_confidence', 0.0)
            analysis_method = project_data.get('launch_analysis_method', 'unknown')
            
            print(f"🌐 [API] AI Analysis Method: {analysis_method}")
            print(f"🌐 [API] Launch Type: {launch_type}")
            print(f"🌐 [API] Confidence: {confidence:.2f}")
            print(f"🌐 [API] AI Command: {launch_command}")
            
            if not launch_command or confidence < 0.3:
                print(f"🌐 [API] Low confidence or missing AI command, using fallback...")
                return self._fallback_launch(project_path, project_name)
            
            print(f"🌐 [API] Step 2: Detecting environment...")
            env_info = self.env_detector.detect_environment(project_path)
            
            logger.launch_attempt(project_name, project_path, env_info['type'])
            
            print(f"🌐 [API] Step 3: Building environment-aware command...")
            
            # Combine working directory with project path
            if working_dir == '.' or not working_dir:
                full_working_dir = project_path
            else:
                full_working_dir = str(Path(project_path) / working_dir)
            
            project_path_quoted = f'"{full_working_dir}"'
            
            # Add launch arguments if any
            full_command = launch_command
            if launch_args:
                full_command += f" {launch_args}"
            
            print(f"🌐 [API] Working Directory: {full_working_dir}")
            print(f"🌐 [API] Base Command: {full_command}")
            print(f"🌐 [API] Environment type: {env_info['type']}")
            
            # Build environment-specific terminal command
            if env_info['type'] == 'conda':
                env_name = env_info.get('name', 'base')
                cmd = f'cd {project_path_quoted} && echo "🚀 Activating conda environment: {env_name}" && conda activate {env_name} && echo "🚀 Running: {full_command}" && {full_command}; echo "\\n📋 Press Enter to close..."; read'
                print(f"🌐 [API] Conda environment: {env_name}")
            elif env_info['type'] == 'venv':
                activate_path = env_info.get('activate_path', '')
                activate_path_quoted = f'"{activate_path}"'
                cmd = f'cd {project_path_quoted} && echo "🚀 Activating virtual environment" && source {activate_path_quoted} && echo "🚀 Running: {full_command}" && {full_command}; echo "\\n📋 Press Enter to close..."; read'
                print(f"🌐 [API] Virtual env activation: {activate_path}")
            elif env_info['type'] == 'poetry':
                cmd = f'cd {project_path_quoted} && echo "🚀 Using Poetry environment" && echo "🚀 Running: poetry run {full_command}" && poetry run {full_command}; echo "\\n📋 Press Enter to close..."; read'
                print(f"🌐 [API] Using Poetry environment")
            elif env_info['type'] == 'pipenv':
                cmd = f'cd {project_path_quoted} && echo "🚀 Using Pipenv environment" && echo "🚀 Running: pipenv run {full_command}" && pipenv run {full_command}; echo "\\n📋 Press Enter to close..."; read'
                print(f"🌐 [API] Using Pipenv environment")
            elif launch_type == 'docker':
                # For docker commands, run them directly without Python environment
                cmd = f'cd {project_path_quoted} && echo "🚀 Running Docker command" && echo "🚀 Command: {full_command}" && {full_command}; echo "\\n📋 Press Enter to close..."; read'
                print(f"🌐 [API] Using Docker")
            else:
                # Default: run with system Python or as-is for non-Python commands
                if full_command.startswith('python'):
                    cmd = f'cd {project_path_quoted} && echo "🚀 Using system Python" && echo "🚀 Running: {full_command}" && {full_command}; echo "\\n📋 Press Enter to close..."; read'
                else:
                    cmd = f'cd {project_path_quoted} && echo "🚀 Running custom command" && echo "🚀 Command: {full_command}" && {full_command}; echo "\\n📋 Press Enter to close..."; read'
                print(f"🌐 [API] Using system environment")
            
            print(f"🌐 [API] Step 4: Executing AI-generated command...")
            print(f"🌐 [API] Final Command: {cmd[:200]}...")
            
            # Use the cross-platform terminal opening function
            terminal_result = self.open_terminal(cmd)
            
            if "Terminal launched successfully!" in terminal_result:
                print(f"🌐 [API] SUCCESS: AI-launched terminal opened")
                logger.launch_success(project_name)
                return f"✅ AI-Launched {project_name} ({launch_type}, confidence: {confidence:.1f}) - Terminal opened"
            else:
                print(f"🌐 [API] ERROR: Failed to open terminal")
                logger.launch_error(project_name, f"AI launch failed: {terminal_result}")
                return f"❌ Failed to start {project_name}: {terminal_result}"
            
        except Exception as e:
            error_msg = str(e)
            print(f"🌐 [API] EXCEPTION: {error_msg}")
            import traceback
            print(f"🌐 [API] Traceback: {traceback.format_exc()}")
            logger.launch_error(project_name, error_msg)
            return f"❌ Error launching project: {error_msg}"
    
    def _fallback_launch(self, project_path: str, project_name: str) -> str:
        """Fallback launch method using traditional approach"""
        print(f"🌐 [API] Using fallback launch method...")
        
        try:
            env_info = self.env_detector.detect_environment(project_path)
            
            if env_info['type'] == 'none':
                error_msg = f"No Python environment detected for {project_name}"
                print(f"🌐 [API] ERROR: {error_msg}")
                logger.launch_error(project_name, error_msg)
                return f"❌ {error_msg}"
            
            # Find main script using traditional method
            main_scripts = ['app.py', 'main.py', 'run.py', 'start.py', 'launch.py', 'webui.py']
            script_path = None
            
            for script in main_scripts:
                potential_path = Path(project_path) / script
                if potential_path.exists():
                    script_path = potential_path
                    break
            
            if not script_path:
                # Try to find any Python file
                py_files = list(Path(project_path).glob('*.py'))
                if py_files:
                    script_path = py_files[0]
                else:
                    error_msg = f"No Python script found in {project_name}"
                    logger.launch_error(project_name, error_msg)
                    return f"❌ {error_msg}"
            
            script_name = script_path.name
            project_path_quoted = f'"{project_path}"'
            
            if env_info['type'] == 'conda':
                env_name = env_info.get('name', 'base')
                cmd = f'cd {project_path_quoted} && conda activate {env_name} && python3 {script_name}; exec bash'
            elif env_info['type'] == 'venv':
                activate_path = env_info.get('activate_path', '')
                cmd = f'cd {project_path_quoted} && source "{activate_path}" && python3 {script_name}; exec bash'
            else:
                cmd = f'cd {project_path_quoted} && python3 {script_name}; exec bash'
            
            # Use the cross-platform terminal opening function
            terminal_result = self.open_terminal(cmd)
            
            if "Terminal launched successfully!" in terminal_result:
                logger.launch_success(project_name)
                return f"✅ Launched {project_name} (Fallback method) - Terminal opened"
            else:
                logger.launch_error(project_name, f"Fallback launch failed: {terminal_result}")
                return f"❌ Fallback launch failed: {terminal_result}"
            
        except Exception as e:
            error_msg = str(e)
            logger.launch_error(project_name, error_msg)
            return f"❌ Error in fallback launch: {error_msg}"
    
    def start(self):
        """Start the API server"""
        print(f"🌐 [API] Starting Launch API Server on port {self.port}...")
        logger.info(f"Starting Launch API Server on port {self.port}")
        
        # Start Flask in a background thread
        def run_flask():
            self.app.run(host='127.0.0.1', port=self.port, debug=False, use_reloader=False)
        
        thread = threading.Thread(target=run_flask, daemon=True)
        thread.start()
        
        print(f"🌐 [API] Launch API Server running at http://127.0.0.1:{self.port}")
        return thread

def start_api_server(port=7871, launcher=None):
    """Start the launch API server"""
    server = LaunchAPIServer(port, launcher)
    return server.start()

if __name__ == "__main__":
    # Test the API server standalone
    server = LaunchAPIServer(7871)
    print("🌐 Starting standalone Launch API Server...")
    server.app.run(host='127.0.0.1', port=7871, debug=True) 