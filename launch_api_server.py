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
                
                # Get project_id or project_path from query parameters
                project_id = request.args.get('project_id')
                project_path = request.args.get('project_path')
                
                if project_id:
                    # Use project_id method (preferred)
                    try:
                        project_index = int(project_id)
                        print(f"🌐 [API] ✅ Project ID: {project_index}")
                    except ValueError:
                        print(f"🌐 [API] ❌ ERROR: Invalid project_id format: {project_id}")
                        return jsonify({"success": False, "error": "Invalid project_id format"}), 400
                elif project_path:
                    # Use project_path method (fallback for legacy compatibility)
                    print(f"🌐 [API] 🔍 Looking up project by path: {project_path}")
                    project_index = None
                    for idx, project in enumerate(self.launcher.current_projects):
                        if project.get('path') == project_path:
                            project_index = idx
                            print(f"🌐 [API] ✅ Found project at index {project_index}")
                            break
                    
                    if project_index is None:
                        print(f"🌐 [API] ❌ ERROR: Project not found with path: {project_path}")
                        return jsonify({"success": False, "error": f"Project not found with path: {project_path}"}), 404
                else:
                    print(f"🌐 [API] ❌ ERROR: No project_id or project_path provided!")
                    return jsonify({"success": False, "error": "Missing project_id or project_path parameter"}), 400
                
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
                
                # Check if we have detailed launch info from the background task
                # For now, just indicate launch initiated
                response_data = {
                    "success": True,
                    "message": f"Launch initiated for {project_name}",
                    "project_id": project_index,
                    "project_name": project_name,
                    "request_time": request_time,
                    "launch_method": "smart_launcher"  # Indicates we use custom launcher if available
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
        
        @self.app.route('/api/toggle-favorite', methods=['POST'])
        def toggle_favorite():
            """Toggle favorite status of a project"""
            try:
                data = request.get_json()
                if not data or 'project_path' not in data:
                    return jsonify({"success": False, "error": "Missing project_path"}), 400
                
                project_path = data['project_path']
                print(f"🌟 [API] Toggle favorite request for: {project_path}")
                
                # Import database here to avoid circular imports
                from project_database import db
                
                new_status = db.toggle_favorite_status(project_path)
                
                print(f"🌟 [API] Favorite status toggled: {new_status}")
                return jsonify({
                    "success": True,
                    "is_favorite": new_status,
                    "project_path": project_path
                })
                
            except Exception as e:
                error_msg = f"Failed to toggle favorite: {str(e)}"
                print(f"🌟 [API] ERROR: {error_msg}")
                return jsonify({"success": False, "error": error_msg}), 500
        
        @self.app.route('/api/toggle-hidden', methods=['POST'])
        def toggle_hidden():
            """Toggle hidden status of a project"""
            try:
                data = request.get_json()
                if not data or 'project_path' not in data:
                    return jsonify({"success": False, "error": "Missing project_path"}), 400
                
                project_path = data['project_path']
                print(f"👻 [API] Toggle hidden request for: {project_path}")
                
                # Import database here to avoid circular imports
                from project_database import db
                
                new_status = db.toggle_hidden_status(project_path)
                
                print(f"👻 [API] Hidden status toggled: {new_status}")
                return jsonify({
                    "success": True,
                    "is_hidden": new_status,
                    "project_path": project_path
                })
                
            except Exception as e:
                error_msg = f"Failed to toggle hidden: {str(e)}"
                print(f"👻 [API] ERROR: {error_msg}")
                return jsonify({"success": False, "error": error_msg}), 500
    
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
        """Execute the project launch using custom launcher or AI-generated command"""
        print(f"🌐 [API] ===== SMART LAUNCH SYSTEM =====")
        print(f"🌐 [API] Project: {project_name}")
        print(f"🌐 [API] Path: {project_path}")
        
        try:
            print(f"🌐 [API] Step 1: Checking for custom launcher...")
            # First, check if a custom launcher exists (highest priority)
            safe_name = "".join(c for c in project_name if c.isalnum() or c in ('-', '_')).strip()
            custom_launcher_path = Path("custom_launchers") / f"{safe_name}.sh"
            
            if custom_launcher_path.exists():
                print(f"🌐 [API] ✅ Found custom launcher: {custom_launcher_path}")
                print(f"🌐 [API] Using custom launcher script for {project_name}")
                
                # Make sure it's executable
                import os
                try:
                    os.chmod(custom_launcher_path, 0o755)
                except:
                    pass  # Ignore permission errors
                
                # Execute the custom launcher directly
                cmd = f'cd "{project_path}" && echo "🚀 Using custom launcher: {custom_launcher_path}" && bash "{custom_launcher_path.absolute()}"'
                print(f"🌐 [API] Custom launcher command: {cmd}")
                
                terminal_result = self.open_terminal(cmd)
                
                if "Terminal launched successfully!" in terminal_result:
                    print(f"🌐 [API] SUCCESS: Custom launcher executed")
                    logger.launch_success(project_name)
                    return f"✅ Custom-Launched {project_name} using {custom_launcher_path.name} - Terminal opened"
                else:
                    print(f"🌐 [API] ERROR: Failed to execute custom launcher")
                    logger.launch_error(project_name, f"Custom launcher failed: {terminal_result}")
                    return f"❌ Failed to start {project_name} with custom launcher: {terminal_result}"
            
            print(f"🌐 [API] ❌ No custom launcher found, generating one...")
            print(f"🌐 [API] Step 2: Creating custom launcher for {project_name}...")
            
            # Generate a custom launcher using AI analysis
            try:
                from qwen_launch_analyzer import QwenLaunchAnalyzer
                analyzer = QwenLaunchAnalyzer()
                
                # Create custom launcher template with AI-generated command
                custom_launcher_path_str = analyzer.create_custom_launcher_template(
                    project_path, project_name, ""  # Let it auto-detect the best command
                )
                
                if custom_launcher_path_str and Path(custom_launcher_path_str).exists():
                    print(f"🌐 [API] ✅ Generated custom launcher: {custom_launcher_path_str}")
                    
                    # Now execute the newly created custom launcher
                    custom_launcher_path = Path(custom_launcher_path_str)
                    
                    # Make sure it's executable
                    import os
                    try:
                        os.chmod(custom_launcher_path, 0o755)
                    except:
                        pass
                    
                    # Execute the newly created custom launcher
                    cmd = f'cd "{project_path}" && echo "🚀 Using newly generated custom launcher: {custom_launcher_path.name}" && bash "{custom_launcher_path.absolute()}"'
                    print(f"🌐 [API] Generated launcher command: {cmd}")
                    
                    terminal_result = self.open_terminal(cmd)
                    
                    if "Terminal launched successfully!" in terminal_result:
                        print(f"🌐 [API] SUCCESS: Generated custom launcher executed")
                        logger.launch_success(project_name)
                        return f"✅ Custom-Launched {project_name} using newly generated {custom_launcher_path.name} - Terminal opened"
                    else:
                        print(f"🌐 [API] ERROR: Failed to execute generated custom launcher")
                        logger.launch_error(project_name, f"Generated custom launcher failed: {terminal_result}")
                        return f"❌ Failed to start {project_name} with generated custom launcher: {terminal_result}"
                else:
                    print(f"🌐 [API] ❌ Failed to generate custom launcher")
                    return f"❌ Failed to generate custom launcher for {project_name}"
                    
            except Exception as e:
                print(f"🌐 [API] ❌ Error generating custom launcher: {str(e)}")
                return f"❌ Error generating custom launcher for {project_name}: {str(e)}"

            
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