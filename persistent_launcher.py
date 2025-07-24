#!/usr/bin/env python3

import gradio as gr
import json
import time
import threading
from pathlib import Path
from typing import Dict, List
from datetime import datetime
import platform
import shutil

from project_database import db
from background_scanner import get_scanner
from environment_detector import EnvironmentDetector
from logger import logger
from launch_api_server import start_api_server
import subprocess

class PersistentLauncher:
    def __init__(self, config: dict):
        self.config = config
        self.env_detector = EnvironmentDetector()
        self.current_projects = []
        self.scanner = None
        
        # UI state tracking
        self.ui_needs_refresh = False
        self.last_ui_update = time.time()
        
    def open_terminal(self, command):
        """Opens a new terminal window and executes the given command - cross-platform"""
        os_name = platform.system()
        print(f"🚀 [TERMINAL] Opening terminal on {os_name} with command: {command[:100]}...")
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
                        print(f"🚀 [TERMINAL] Found terminal: {terminal}")
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
                
            print(f"🚀 [TERMINAL] Terminal opened successfully")
            logger.info("Terminal opened successfully")
            return "Terminal launched successfully!"
            
        except Exception as e:
            error_msg = f"Error launching terminal: {str(e)}"
            print(f"🚀 [TERMINAL] ERROR: {error_msg}")
            logger.error(error_msg)
            return error_msg

    def initialize(self):
        """Initialize the launcher - load from database and start background scanner"""
        logger.info("Initializing Persistent AI Launcher...")
        
        # Load existing projects from database
        self.load_projects_from_db()
        
        # Start background scanner
        self.scanner = get_scanner(self.config, self.on_scanner_update)
        self.scanner.start()
        
        logger.info(f"Launcher initialized with {len(self.current_projects)} projects")
    
    def load_projects_from_db(self):
        """Load projects from database"""
        try:
            self.current_projects = db.get_all_projects(active_only=True)
            logger.info(f"Loaded {len(self.current_projects)} projects from database")
            self.last_ui_update = time.time()
        except Exception as e:
            logger.error(f"Error loading projects from database: {e}")
            self.current_projects = []
    
    def filter_projects(self, search_query: str) -> List[Dict]:
        """Filter projects based on search query with fuzzy matching"""
        if not search_query or not search_query.strip():
            return self.current_projects
        
        search_terms = search_query.lower().strip().split()
        filtered_projects = []
        
        for project in self.current_projects:
            # Create searchable text from project data - ensure all fields are strings
            searchable_fields = [
                str(project.get('name', '') or ''),
                str(project.get('display_name', '') or ''),
                str(project.get('description', '') or ''),
                str(project.get('tooltip', '') or ''),
                str(project.get('path', '') or '').replace('/', ' ').replace('\\', ' '),  # Make paths searchable
                str(project.get('environment_type', '') or ''),
                str(project.get('main_script', '') or ''),
            ]
            
            # Filter out any remaining None or empty values
            searchable_fields = [field for field in searchable_fields if field and field != 'None']
            searchable_text = " ".join(searchable_fields).lower()
            
            # Calculate match score
            match_score = 0
            max_possible_score = len(search_terms)
            
            for term in search_terms:
                if term in searchable_text:
                    match_score += 1
                    # Boost score for exact name matches
                    if term in project.get('name', '').lower():
                        match_score += 0.5
                    # Boost score for environment type matches
                    if term == project.get('environment_type', '').lower():
                        match_score += 0.3
            
            # Include project if it matches all terms or has a high partial match
            if match_score >= max_possible_score or (match_score / max_possible_score) >= 0.7:
                # Add match score for potential sorting
                project_copy = project.copy()
                project_copy['_match_score'] = match_score
                filtered_projects.append(project_copy)
        
        # Sort by match score (highest first)
        filtered_projects.sort(key=lambda x: x.get('_match_score', 0), reverse=True)
        
        return filtered_projects
    
    def on_scanner_update(self, event_type: str, data: Dict):
        """Handle updates from background scanner"""
        try:
            if event_type == 'project_added':
                self.current_projects.append(data)
                self.ui_needs_refresh = True
                logger.info(f"Added new project to UI: {data.get('name', 'Unknown')}")
                
            elif event_type == 'project_updated':
                # Update existing project in list
                for i, project in enumerate(self.current_projects):
                    if project['path'] == data['path']:
                        self.current_projects[i].update(data)
                        break
                self.ui_needs_refresh = True
                logger.info(f"Updated project in UI: {data.get('name', 'Unknown')}")
                
            elif event_type == 'scan_complete':
                scan_info = data
                logger.info(f"Scan complete: {scan_info['scan_type']} - "
                          f"Found: {scan_info['projects_found']}, "
                          f"Updated: {scan_info['projects_updated']}")
                
                # Reload projects to ensure UI is in sync
                self.load_projects_from_db()
                self.ui_needs_refresh = True
                
        except Exception as e:
            logger.error(f"Error handling scanner update: {e}")
    
    def _create_expandable_description(self, description: str) -> str:
        """Create an expandable description using HTML5 details/summary elements"""
        # Ensure description is always a string
        description = str(description or 'AI/ML Project')
        
        # Define truncation length for consistent card heights
        TRUNCATE_LENGTH = 150
        
        if not description or len(description.strip()) <= TRUNCATE_LENGTH:
            # Short descriptions don't need expansion
            return f'<div style="color: #2c3e50 !important; line-height: 1.4;">{description}</div>'
        
        # Create truncated preview (first ~150 characters, cut at word boundary)
        truncated = description[:TRUNCATE_LENGTH]
        # Find the last space to avoid cutting words
        last_space = truncated.rfind(' ')
        if last_space > TRUNCATE_LENGTH * 0.8:  # Only cut at word boundary if it's not too short
            truncated = truncated[:last_space]
        
        preview_text = truncated.strip() + "..."
        
        return f"""
        <details style="color: #2c3e50 !important; line-height: 1.4; margin: 0;">
            <summary style="
                cursor: pointer;
                color: #2c3e50 !important;
                font-weight: normal;
                list-style: none;
                outline: none;
                user-select: none;
                padding: 2px 0;
                margin: 0;
                position: relative;
                display: block;
            ">
                <span style="color: #2c3e50 !important;">{preview_text}</span>
                <span style="
                    color: #007bff !important;
                    font-size: 11px;
                    text-decoration: underline;
                    margin-left: 8px;
                    font-weight: normal;
                "> ▼ Show full description</span>
            </summary>
            <div style="
                color: #2c3e50 !important;
                margin-top: 6px;
                line-height: 1.4;
                padding: 8px 0;
                border-top: 1px solid #e0e0e0;
                background: #f9f9f9;
                padding: 8px 12px;
                border-radius: 6px;
            ">{description}</div>
        </details>
        """
    
    def create_project_card(self, project: Dict, index: int, api_port: int = 7871) -> str:
        """Create HTML for a single project card"""
        # Get status indicators
        env_type = project.get('environment_type', 'unknown')
        main_script = project.get('main_script', 'Unknown')
        last_scanned = project.get('last_scanned', '')
        dirty_flag = project.get('dirty_flag', 1)
        
        # Format last scanned time
        if last_scanned:
            try:
                if isinstance(last_scanned, str):
                    scan_time = datetime.fromisoformat(last_scanned)
                else:
                    scan_time = datetime.fromtimestamp(float(last_scanned))
                time_str = scan_time.strftime("%m/%d %H:%M")
            except:
                time_str = "Unknown"
        else:
            time_str = "Never"
        
        # Status badges
        status_badges = []
        if dirty_flag:
            status_badges.append('<span style="background: #ff6b6b; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px;">NEEDS UPDATE</span>')
        else:
            status_badges.append('<span style="background: #51cf66; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px;">UP TO DATE</span>')
        
        if project.get('is_git', False):
            status_badges.append('<span style="background: #339af0; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px;">GIT</span>')
        
        # Description handling - ensure we have a valid string
        description = project.get('description') or project.get('tooltip') or 'AI/ML Project'
        if not description or description == 'No description available' or description == 'None':
            description = project.get('tooltip') or f"AI project: {project.get('name', 'Unknown')}"
        
        # Ensure description is a string
        description = str(description or 'AI/ML Project')
        
        # Create unique IDs for this card
        card_id = f"card_{index}"
        desc_id = f"desc_{index}"
        btn_id = f"btn_{index}"
        launch_id = f"launch_{index}"
        
        # Escape project path for JavaScript - avoid backslashes in f-strings
        project_path_safe = str(project.get('path', '')).replace('\\', '/').replace("'", "&apos;")
        project_name_safe = str(project.get('name', 'Unknown')).replace("'", "&apos;")

        return f"""
        <div class="project-card" id="{card_id}" style="
            border: 1px solid #e0e0e0; 
            border-radius: 12px; 
            padding: 16px; 
            margin: 8px;
            background: linear-gradient(145deg, #ffffff, #f8f9fa);
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: all 0.2s ease;
            position: relative;
        ">
            <div style="display: flex; align-items: flex-start; gap: 12px;">
                <img src="{project.get('icon_data', '')}" style="
                    width: 64px; height: 64px; 
                    border-radius: 8px; 
                    border: 2px solid #e0e0e0;
                    flex-shrink: 0;
                " />
                <div style="flex: 1; min-width: 0;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                        <h3 style="margin: 0; font-size: 16px; color: #2c3e50; font-weight: 600; flex: 1;">
                            {str(project.get('name', 'Unknown Project'))}
                        </h3>
                        <a href="http://localhost:{api_port}/launch?project_id={index}" 
                           target="_blank" 
                           style="
                            background: linear-gradient(135deg, #007bff, #0056b3);
                            color: white; 
                            border: none; 
                            padding: 8px 16px; 
                            border-radius: 20px; 
                            cursor: pointer; 
                            font-size: 12px;
                            font-weight: 600;
                            box-shadow: 0 2px 4px rgba(0,123,255,0.3);
                            transition: all 0.2s ease;
                            margin-left: 12px;
                            text-decoration: none;
                            display: inline-block;
                        " onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 4px 8px rgba(0,123,255,0.4)'"
                           onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 4px rgba(0,123,255,0.3)'">
                            🚀 Launch
                        </a>
                    </div>
                    <div style="margin-bottom: 8px;">
                        {' '.join(status_badges)}
                    </div>
                    <div style="
                        font-size: 12px; color: #2c3e50 !important; margin: 0 0 8px 0; 
                        line-height: 1.4;
                    ">
                        {self._create_expandable_description(description)}
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #868e96;">
                        <span>🐍 {env_type} • 📝 {main_script}</span>
                        <span>Last: {time_str}</span>
                    </div>
                </div>
            </div>
        </div>
        """
    
    def create_projects_grid(self, projects: List[Dict], api_port: int = 7871) -> str:
        """Create responsive grid of project cards"""
        if not projects:
            return """
            <div style="text-align: center; padding: 40px; color: #6c757d;">
                <h3>No projects found</h3>
                <p>The background scanner will automatically discover projects in your configured directories.</p>
            </div>
            """
        
        grid_html = f"""
        <div style="
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); 
            gap: 16px; 
            padding: 16px;
        ">
        """
        
        for i, project in enumerate(projects):
            grid_html += self.create_project_card(project, i, api_port)
        
        grid_html += "</div>"
        
        # No JavaScript needed - using direct HTML links for API calls
        
        return grid_html
    
    def launch_project(self, project_path: str, project_name: str) -> str:
        """Launch a project using AI-generated launch command"""
        print(f"🚀 [TERMINAL] ===== AI-POWERED LAUNCH =====")
        print(f"🚀 [TERMINAL] Project: {project_name}")
        print(f"🚀 [TERMINAL] Path: {project_path}")
        
        try:
            print(f"🚀 [TERMINAL] Step 1: Getting project from database...")
            # Get project data from database to access AI-generated launch command
            project_data = db.get_project_by_path(project_path)
            
            if not project_data:
                print(f"🚀 [TERMINAL] Project not found in database, using fallback...")
                return self._fallback_launch(project_path, project_name)
            
            # Get AI-generated launch information
            launch_command = project_data.get('launch_command')
            launch_type = project_data.get('launch_type', 'unknown')
            working_dir = project_data.get('launch_working_directory', '.')
            launch_args = project_data.get('launch_args', '')
            confidence = project_data.get('launch_confidence', 0.0)
            analysis_method = project_data.get('launch_analysis_method', 'unknown')
            
            print(f"🚀 [TERMINAL] AI Analysis Method: {analysis_method}")
            print(f"🚀 [TERMINAL] Launch Type: {launch_type}")
            print(f"🚀 [TERMINAL] Confidence: {confidence:.2f}")
            print(f"🚀 [TERMINAL] AI Command: {launch_command}")
            
            if not launch_command or confidence < 0.3:
                print(f"🚀 [TERMINAL] Low confidence or missing AI command, using fallback...")
                return self._fallback_launch(project_path, project_name)
            
            print(f"🚀 [TERMINAL] Step 2: Detecting environment...")
            env_detector = EnvironmentDetector()
            env_info = env_detector.detect_environment(project_path)
            
            logger.launch_attempt(project_name, project_path, env_info['type'])
            
            print(f"🚀 [TERMINAL] Step 3: Building environment-aware command...")
            
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
            
            print(f"🚀 [TERMINAL] Working Directory: {full_working_dir}")
            print(f"🚀 [TERMINAL] Base Command: {full_command}")
            print(f"🚀 [TERMINAL] Environment type: {env_info['type']}")
            
            # Build environment-specific terminal command
            if env_info['type'] == 'conda':
                env_name = env_info.get('name', 'base')
                cmd = f'cd {project_path_quoted} && echo "🚀 Activating conda environment: {env_name}" && conda activate {env_name} && echo "🚀 Running: {full_command}" && {full_command}; echo "\\n📋 Press Enter to close..."; read'
                print(f"🚀 [TERMINAL] Conda environment: {env_name}")
            elif env_info['type'] == 'venv':
                activate_path = env_info.get('activate_path', '')
                activate_path_quoted = f'"{activate_path}"'
                cmd = f'cd {project_path_quoted} && echo "🚀 Activating virtual environment" && source {activate_path_quoted} && echo "🚀 Running: {full_command}" && {full_command}; echo "\\n📋 Press Enter to close..."; read'
                print(f"🚀 [TERMINAL] Virtual env activation: {activate_path}")
            elif env_info['type'] == 'poetry':
                cmd = f'cd {project_path_quoted} && echo "🚀 Using Poetry environment" && echo "🚀 Running: poetry run {full_command}" && poetry run {full_command}; echo "\\n📋 Press Enter to close..."; read'
                print(f"🚀 [TERMINAL] Using Poetry environment")
            elif env_info['type'] == 'pipenv':
                cmd = f'cd {project_path_quoted} && echo "🚀 Using Pipenv environment" && echo "🚀 Running: pipenv run {full_command}" && pipenv run {full_command}; echo "\\n📋 Press Enter to close..."; read'
                print(f"🚀 [TERMINAL] Using Pipenv environment")
            elif launch_type == 'docker':
                # For docker commands, run them directly without Python environment
                cmd = f'cd {project_path_quoted} && echo "🚀 Running Docker command" && echo "🚀 Command: {full_command}" && {full_command}; echo "\\n📋 Press Enter to close..."; read'
                print(f"🚀 [TERMINAL] Using Docker")
            else:
                # Default: run with system Python or as-is for non-Python commands
                if full_command.startswith('python'):
                    cmd = f'cd {project_path_quoted} && echo "🚀 Using system Python" && echo "🚀 Running: {full_command}" && {full_command}; echo "\\n📋 Press Enter to close..."; read'
                else:
                    cmd = f'cd {project_path_quoted} && echo "🚀 Running custom command" && echo "🚀 Command: {full_command}" && {full_command}; echo "\\n📋 Press Enter to close..."; read'
                print(f"🚀 [TERMINAL] Using system environment")
            
            print(f"🚀 [TERMINAL] Step 4: Executing AI-generated command...")
            print(f"🚀 [TERMINAL] Final Command: {cmd[:200]}...")
            
            # Use the new cross-platform terminal opening function
            terminal_result = self.open_terminal(cmd)
            
            if "Terminal launched successfully!" in terminal_result:
                print(f"🚀 [TERMINAL] SUCCESS: AI-launched terminal opened")
                logger.launch_success(project_name)
                return f"✅ AI-Launched {project_name} ({launch_type}, confidence: {confidence:.1f}) - Terminal opened"
            else:
                print(f"🚀 [TERMINAL] ERROR: Failed to open terminal")
                logger.launch_error(project_name, f"AI launch failed: {terminal_result}")
                return f"❌ Failed to start {project_name}: {terminal_result}"
            
        except Exception as e:
            error_msg = str(e)
            print(f"🚀 [TERMINAL] EXCEPTION: {error_msg}")
            import traceback
            print(f"🚀 [TERMINAL] Traceback: {traceback.format_exc()}")
            logger.launch_error(project_name, error_msg)
            return f"❌ Error launching project: {error_msg}"
    
    def _fallback_launch(self, project_path: str, project_name: str) -> str:
        """Fallback launch method using traditional approach"""
        print(f"🚀 [TERMINAL] Using fallback launch method...")
        
        try:
            env_detector = EnvironmentDetector()
            env_info = env_detector.detect_environment(project_path)
            
            if env_info['type'] == 'none':
                error_msg = f"No Python environment detected for {project_name}"
                print(f"🚀 [TERMINAL] ERROR: {error_msg}")
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
            
            # Use the new cross-platform terminal opening function
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

    def launch_project_background(self, project_path: str, project_name: str, launch_id: int = 0) -> str:
        """Launch a project in the background without blocking the UI"""
        print(f"🚀 [TERMINAL] launch_project_background() called")
        print(f"🚀 [TERMINAL]   Project: {project_name}")
        print(f"🚀 [TERMINAL]   Path: {project_path}")
        print(f"🚀 [TERMINAL]   Launch ID: {launch_id}")
        logger.info(f"🚀 launch_project_background called - Name: {project_name}, Path: {project_path}, ID: {launch_id}")
        
        def run_launch():
            try:
                print(f"🚀 [TERMINAL] Background thread started for {project_name}")
                logger.info(f"[{launch_id}] Background thread started for {project_name}")
                
                result = self.launch_project(project_path, project_name)
                
                print(f"🚀 [TERMINAL] Background launch completed: {result}")
                logger.info(f"[{launch_id}] Background launch completed: {project_name}")
                return result
            except Exception as e:
                error_msg = f"❌ Error launching {project_name}: {str(e)}"
                print(f"🚀 [TERMINAL] Background launch FAILED: {error_msg}")
                logger.error(f"[{launch_id}] Background launch failed: {error_msg}")
                return error_msg
        
        print(f"🚀 [TERMINAL] Starting background thread...")
        # Start the launch in a background thread
        thread = threading.Thread(target=run_launch, daemon=True)
        thread.start()
        print(f"🚀 [TERMINAL] Background thread started successfully")
        
        return f"✅ {project_name} is starting... (Background launch #{launch_id})"

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

def main(api_port=7871):
    """Main application entry point"""
    config = load_config()
    launcher = PersistentLauncher(config)
    
    # Initialize the launcher
    launcher.initialize()
    
    # Start the API server with launcher instance
    print(f"🚀 [TERMINAL] Starting Launch API Server on port {api_port}...")
    api_server_thread = start_api_server(port=api_port, launcher=launcher)
    print(f"🚀 [TERMINAL] Launch API Server started on port {api_port}")
    
    # Get initial stats
    stats = db.get_stats()
    
    with gr.Blocks(title="🚀 Persistent AI Launcher", theme=gr.themes.Soft()) as app:
        # Add custom CSS for sticky search bar
        gr.HTML("""
        <style>
        .search-container {
            position: sticky !important;
            top: 0 !important;
            z-index: 1000 !important;
            background: linear-gradient(135deg, #ffffff, #f8f9fa) !important;
            padding: 15px 20px !important;
            border-bottom: 2px solid #e0e0e0 !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
            margin: -20px -20px 20px -20px !important;
            backdrop-filter: blur(10px) !important;
        }
        .search-input {
            width: 100% !important;
            max-width: 800px !important;
            margin: 0 auto !important;
            padding: 14px 20px 14px 50px !important;
            border: 2px solid #007bff !important;
            border-radius: 30px !important;
            font-size: 16px !important;
            outline: none !important;
            transition: all 0.3s ease !important;
            background: white !important;
            background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="%23007bff" viewBox="0 0 16 16"><path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z"/></svg>') !important;
            background-repeat: no-repeat !important;
            background-position: 18px center !important;
            background-size: 16px !important;
        }
        .search-input:focus {
            border-color: #0056b3 !important;
            box-shadow: 0 0 15px rgba(0,123,255,0.4) !important;
            transform: translateY(-1px) !important;
        }
        .search-label {
            margin-bottom: 10px !important;
            font-weight: 600 !important;
            color: #2c3e50 !important;
            text-align: center !important;
            font-size: 18px !important;
        }
        .search-container .gradio-textbox {
            border: none !important;
            box-shadow: none !important;
        }
        .search-container .gradio-textbox input {
            border: 2px solid #007bff !important;
            border-radius: 30px !important;
        }
        #clear_search {
            background: #dc3545 !important;
            border: 2px solid #dc3545 !important;
            border-radius: 50% !important;
            width: 40px !important;
            height: 40px !important;
            padding: 0 !important;
            margin-left: 10px !important;
            color: white !important;
            font-size: 14px !important;
            transition: all 0.3s ease !important;
            cursor: pointer !important;
        }
        
        /* Force text colors to be visible regardless of theme */
        .project-card * {
            color: #2c3e50 !important;
        }
        .project-card h3 {
            color: #2c3e50 !important;
        }
        .project-card details, .project-card summary, .project-card span, .project-card div:not(.project-card) {
            color: #2c3e50 !important;
        }
        .project-card details summary span:last-child {
            color: #007bff !important;
        }
        .project-card details[open] summary span:last-child {
            color: #007bff !important;
        }
        #clear_search:hover {
            background: #c82333 !important;
            border-color: #c82333 !important;
            transform: scale(1.1) !important;
        }
        @media (max-width: 768px) {
            .search-container {
                padding: 12px 15px !important;
                margin: -15px -15px 15px -15px !important;
            }
            .search-input {
                padding: 12px 16px 12px 45px !important;
                font-size: 14px !important;
            }
            .search-label {
                font-size: 16px !important;
            }
            #clear_search {
                width: 35px !important;
                height: 35px !important;
                font-size: 12px !important;
                margin-left: 8px !important;
            }
        }
        
        /* Force readable text colors in project cards */
        .project-card,
        .project-card *,
        .project-card div,
        .project-card p,
        .project-card span {
            color: #2c3e50 !important;
        }
        
        /* Specific overrides for project descriptions */
        .project-card div[id*="desc_"] {
            color: #2c3e50 !important;
        }
        
        .project-card div[id*="desc_"] * {
            color: #2c3e50 !important;
        }
        
        /* Override any Gradio theme text colors in project cards */
        .project-card [style*="color"] {
            color: #2c3e50 !important;
        }
        
        /* Force dark text on light backgrounds globally for project area */
        div[style*="background: linear-gradient(145deg, #ffffff, #f8f9fa)"] *,
        div[style*="background: linear-gradient(145deg, #ffffff, #f8f9fa)"] div,
        div[style*="background: linear-gradient(145deg, #ffffff, #f8f9fa)"] p,
        div[style*="background: linear-gradient(145deg, #ffffff, #f8f9fa)"] span {
            color: #2c3e50 !important;
        }
        </style>
        """)
        
        # Sticky search bar with keyboard shortcuts
        gr.HTML("""
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Add keyboard shortcuts
            document.addEventListener('keydown', function(e) {
                // Ctrl+F or Cmd+F to focus search
                if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                    e.preventDefault();
                    const searchInput = document.querySelector('#project_search input');
                    if (searchInput) {
                        searchInput.focus();
                        searchInput.select();
                    }
                }
                // Escape to clear search
                if (e.key === 'Escape') {
                    const searchInput = document.querySelector('#project_search input');
                    if (searchInput && searchInput === document.activeElement) {
                        const clearBtn = document.querySelector('#clear_search');
                        if (clearBtn) clearBtn.click();
                    }
                }
            });
        });
        </script>
        """)
        
        # Sticky search bar
        with gr.Row(elem_classes="search-container"):
            with gr.Column():
                gr.HTML('<div class="search-label">🔍 Search Projects <span style="font-size: 12px; color: #6c757d;">(Ctrl+F to focus, Esc to clear)</span></div>')
                with gr.Row():
                    with gr.Column(scale=9):
                        search_input = gr.Textbox(
                            placeholder="Type to search projects by name, description, path, or environment...",
                            elem_classes="search-input",
                            elem_id="project_search",
                            show_label=False,
                            container=False
                        )
                    with gr.Column(scale=1, min_width=60):
                        clear_search_btn = gr.Button("✖️", size="sm", elem_id="clear_search")
        
        gr.Markdown("# 🚀 Persistent AI Project Launcher")
        gr.Markdown("Automatically discovers, tracks, and launches your AI projects with persistent caching and background scanning.")
        
        # Status and controls
        with gr.Row():
            with gr.Column(scale=2):
                status_display = gr.Markdown(f"""
**Status:** Running • **Projects:** {stats['active_projects']} • **Pending Updates:** {stats['dirty_projects']}
                """)
            
            with gr.Column(scale=1):
                with gr.Row():
                    manual_scan_btn = gr.Button("🔄 Manual Scan", size="sm")
                    process_dirty_btn = gr.Button("🤖 Process Updates", size="sm")
                    refresh_btn = gr.Button("♻️ Refresh", size="sm")
        
        # Projects display
        projects_display = gr.HTML(launcher.create_projects_grid(launcher.current_projects, api_port))
        
        # Launch output for showing launch results
        with gr.Row():
            launch_output = gr.Textbox(label="Launch Output", interactive=False, elem_id="launch_output")
            project_details = gr.Markdown("Click on a project name to see details")
        
        # Hidden components for instant launches
        with gr.Row(visible=False):
            instant_launch_input = gr.Textbox(elem_id="instant_launch_data")
            project_name_input = gr.Textbox(elem_id="project_name_data")
            project_path_input = gr.Textbox(elem_id="project_path_data")
            launch_trigger = gr.Button("Launch", elem_id="launch_trigger")
        
        # TEST: Simple communication test
        with gr.Row():
            test_input = gr.Textbox(label="Communication Test", placeholder="Type anything and press Enter to test", elem_id="test_input")
            test_output = gr.Textbox(label="Test Output", interactive=False)
        
        # TEST: JavaScript function test
        with gr.Row():
            gr.HTML(f"""
            <div style="padding: 10px; border: 2px solid #007bff; border-radius: 8px; background: #f0f8ff;">
                <h4>🧪 Launch System Diagnostics</h4>
                <button onclick="console.log('TEST: Calling launchProject...'); launchProject('TEST_PROJECT', '/test/path'); return false;" 
                        style="background: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; margin: 5px;">
                    Test launchProject() Function
                </button>
                <button onclick="console.log('TEST: Console test'); alert('Console test works!'); return false;" 
                        style="background: #17a2b8; color: white; border: none; padding: 8px 16px; border-radius: 4px; margin: 5px;">
                    Test Console/Alert
                </button>
                <button onclick="fetch('http://localhost:{api_port}/test').then(r=>r.json()).then(d=>console.log('API Test:', d)).catch(e=>console.log('API Error:', e)); return false;" 
                        style="background: #ffc107; color: black; border: none; padding: 8px 16px; border-radius: 4px; margin: 5px;">
                    Test API Connection
                </button>
                <p style="font-size: 12px; color: #666; margin: 5px 0;">
                    Click buttons above and check browser console (F12) + terminal for debug logs.
                </p>
                <p style="font-size: 12px; color: #666; margin: 5px 0;">
                    <strong>API URL:</strong> http://localhost:{api_port}/launch
                </p>
            </div>
            """)
        
        def test_communication(test_message):
            """Simple test to verify JavaScript→Python communication"""
            print(f"🧪 [TEST] ==========================================")
            print(f"🧪 [TEST] GRADIO COMMUNICATION TEST")
            print(f"🧪 [TEST] Message received: {repr(test_message)}")
            print(f"🧪 [TEST] Timestamp: {time.strftime('%H:%M:%S')}")
            print(f"🧪 [TEST] ==========================================")
            logger.info(f"🧪 TEST: Received message: {test_message}")
            return f"✅ Received: {test_message} at {time.strftime('%H:%M:%S')}"
        
        # Button click logging now handled by API server
        
        test_input.submit(
            test_communication,
            inputs=[test_input],
            outputs=[test_output]
        )
        
        # Launch buttons now work via direct API calls - no complex Gradio communication needed
        
        # Advanced controls
        with gr.Accordion("🛠️ Advanced Controls", open=False):
            with gr.Row():
                view_logs_btn = gr.Button("View Scan History")
                cleanup_btn = gr.Button("Cleanup Old Data")
            
            scan_history = gr.Textbox(label="Recent Scan Sessions", lines=5, interactive=False)
        
        # Event handlers
        def refresh_display():
            launcher.load_projects_from_db()
            grid_html = launcher.create_projects_grid(launcher.current_projects, api_port)
            stats = db.get_stats()
            status_md = f"**Status:** Running • **Projects:** {stats['active_projects']} • **Pending Updates:** {stats['dirty_projects']}"
            launcher.ui_needs_refresh = False
            
            return grid_html, status_md
        
        def manual_scan():
            launcher.scanner.trigger_scan()
            return "Manual scan initiated..."
        
        def process_dirty():
            launcher.scanner.trigger_dirty_cleanup()
            return "Processing dirty projects..."
        
        def search_projects(search_query):
            """Filter and display projects based on search query"""
            try:
                print(f"🚀 [TERMINAL] Search triggered with query: '{search_query}'")
                
                filtered_projects = launcher.filter_projects(search_query)
                grid_html = launcher.create_projects_grid(filtered_projects, api_port)
                
                # Update status to show filtered count
                total_projects = len(launcher.current_projects)
                filtered_count = len(filtered_projects)
                
                print(f"🚀 [TERMINAL] Search results: {filtered_count} of {total_projects} projects")
                
                if search_query and search_query.strip():
                    if filtered_count == 0:
                        search_status = f"🔍 **No Results:** No projects match '{search_query}' • Total: {total_projects} projects"
                    elif filtered_count == total_projects:
                        search_status = f"🔍 **All Projects:** Showing all {total_projects} projects"
                    else:
                        search_status = f"🔍 **Search Results:** {filtered_count} of {total_projects} projects match '{search_query}'"
                else:
                    stats = db.get_stats()
                    search_status = f"**Status:** Running • **Projects:** {stats['active_projects']} • **Pending Updates:** {stats['dirty_projects']}"
                
                return grid_html, search_status
                
            except Exception as e:
                print(f"🚀 [TERMINAL] Search error: {str(e)}")
                import traceback
                print(f"🚀 [TERMINAL] Search traceback: {traceback.format_exc()}")
                
                # Return error message and current projects
                error_msg = f"🔍 **Search Error:** {str(e)} • Showing all projects"
                grid_html = launcher.create_projects_grid(launcher.current_projects)
                return grid_html, error_msg
        
        def clear_search():
            """Clear the search and show all projects"""
            grid_html = launcher.create_projects_grid(launcher.current_projects, api_port)
            stats = db.get_stats()
            status_md = f"**Status:** Running • **Projects:** {stats['active_projects']} • **Pending Updates:** {stats['dirty_projects']}"
            return "", grid_html, status_md
        
        def handle_instant_launch(launch_data_json):
            """Handle instant project launches from the UI"""
            print(f"\n🚀 [TERMINAL] === LAUNCH BUTTON CLICKED ===")
            print(f"🚀 [TERMINAL] handle_instant_launch() called")
            print(f"🚀 [TERMINAL] Raw data received: {repr(launch_data_json)}")
            print(f"🚀 [TERMINAL] Data type: {type(launch_data_json)}")
            print(f"🚀 [TERMINAL] Data length: {len(str(launch_data_json)) if launch_data_json else 0}")
            logger.info(f"🚀 LAUNCH BUTTON CLICKED - handle_instant_launch called with data: {launch_data_json}")
            
            if not launch_data_json:
                print(f"🚀 [TERMINAL] ERROR: No launch data provided")
                logger.warning("LAUNCH BUTTON: No launch data provided")
                return "❌ No launch data received"
                
            try:
                import json
                launch_data = json.loads(launch_data_json)
                project_name = launch_data.get('project_name', '')
                project_path = launch_data.get('project_path', '')
                launch_id = launch_data.get('launch_id', 0)
                
                print(f"🚀 [TERMINAL] Parsed launch request:")
                print(f"🚀 [TERMINAL]   Project: {project_name}")
                print(f"🚀 [TERMINAL]   Path: {project_path}")
                print(f"🚀 [TERMINAL]   Launch ID: {launch_id}")
                
                logger.info(f"🚀 Parsed launch data - Name: {project_name}, Path: {project_path}, ID: {launch_id}")
                
                if not project_name or not project_path:
                    print(f"🚀 [TERMINAL] ERROR: Missing project name or path")
                    logger.error("Invalid launch data: missing name or path")
                    return "❌ Invalid launch data"
                
                print(f"🚀 [TERMINAL] Calling launch_project_background()...")
                # Launch in background immediately
                result = launcher.launch_project_background(project_path, project_name, launch_id)
                print(f"🚀 [TERMINAL] Background launch result: {result}")
                logger.info(f"[{launch_id}] Instant launch triggered: {project_name}")
                return result
                
            except Exception as e:
                error_msg = f"❌ Launch error: {str(e)}"
                print(f"🚀 [TERMINAL] EXCEPTION: {error_msg}")
                logger.error(f"Instant launch failed: {error_msg}")
                return error_msg
        

        

        
        def get_scan_history():
            sessions = db.get_scan_history(limit=10)
            history_text = ""
            
            for session in sessions:
                start_time = session.get('start_time', 'Unknown')
                scan_type = session.get('session_id', 'Unknown').split('_')[0]
                found = session.get('projects_found', 0)
                updated = session.get('projects_updated', 0)
                status = session.get('status', 'unknown')
                
                history_text += f"{start_time} | {scan_type.upper()} | Found: {found}, Updated: {updated} | {status}\n"
            
            return history_text or "No scan history available"
        
        # Wire up events
        refresh_btn.click(
            refresh_display,
            outputs=[projects_display, status_display]
        )
        
        manual_scan_btn.click(
            manual_scan,
            outputs=[launch_output]
        )
        
        process_dirty_btn.click(
            process_dirty,
            outputs=[launch_output]
        )
        
        view_logs_btn.click(
            get_scan_history,
            outputs=[scan_history]
        )
        
        # Connect search input for real-time filtering
        search_input.change(
            search_projects,
            inputs=[search_input],
            outputs=[projects_display, status_display]
        )
        
        # Add debug logging for input changes
        def log_input_change(value, component_name):
            print(f"🚀 [TERMINAL] Input change detected - {component_name}: {repr(value)}")
            logger.info(f"Input change - {component_name}: {value}")
            return value
        
        instant_launch_input.change(
            lambda x: log_input_change(x, "instant_launch_input"),
            inputs=[instant_launch_input],
            outputs=[]
        )
        
        project_name_input.change(
            lambda x: log_input_change(x, "project_name_input"),
            inputs=[project_name_input],
            outputs=[]
        )
        
        project_path_input.change(
            lambda x: log_input_change(x, "project_path_input"),
            inputs=[project_path_input],
            outputs=[]
        )
        
        # Connect clear search button
        clear_search_btn.click(
            clear_search,
            outputs=[search_input, projects_display, status_display]
        )
        
        # Handle instant launches - Method 1: JSON input
        instant_launch_input.change(
            handle_instant_launch,
            inputs=[instant_launch_input],
            outputs=[launch_output]
        )
        
        # Handle instant launches - Method 2: Separate inputs + trigger
        def handle_separate_launch(project_name, project_path):
            """Handle launch using separate name/path inputs"""
            print(f"\n🚀 [TERMINAL] === LAUNCH BUTTON CLICKED (SEPARATE METHOD) ===")
            print(f"🚀 [TERMINAL] handle_separate_launch() called")
            print(f"🚀 [TERMINAL] Separate method - Project: {repr(project_name)}")
            print(f"🚀 [TERMINAL] Separate method - Path: {repr(project_path)}")
            print(f"🚀 [TERMINAL] Name type: {type(project_name)}, Path type: {type(project_path)}")
            logger.info(f"🚀 LAUNCH BUTTON CLICKED (SEPARATE) - Name: {project_name}, Path: {project_path}")
            
            if not project_name or not project_path:
                print(f"🚀 [TERMINAL] ERROR: Missing project name or path")
                logger.error("LAUNCH BUTTON: Missing project name or path in separate launch")
                return "❌ Missing project name or path"
            
            try:
                print(f"🚀 [TERMINAL] Calling launch_project_background() via separate method...")
                result = launcher.launch_project_background(project_path, project_name, 0)
                print(f"🚀 [TERMINAL] Separate launch result: {result}")
                logger.info(f"Separate launch triggered: {project_name}")
                return result
            except Exception as e:
                error_msg = f"❌ Launch error: {str(e)}"
                print(f"🚀 [TERMINAL] EXCEPTION in separate launch: {error_msg}")
                logger.error(f"Separate launch failed: {error_msg}")
                return error_msg
        
        launch_trigger.click(
            handle_separate_launch,
            inputs=[project_name_input, project_path_input],
            outputs=[launch_output]
        )
        
        # Auto-refresh using periodic check - compatible with Gradio 3.41.2
        auto_refresh_state = gr.State(time.time())
        
        def check_for_updates(last_check_time):
            """Periodic check for UI updates"""
            current_time = time.time()
            
            # Only refresh if needed and it's been at least 10 seconds
            if (launcher.ui_needs_refresh and (current_time - last_check_time > 10)) or (current_time - launcher.last_ui_update > 60):
                grid_html = launcher.create_projects_grid(launcher.current_projects, api_port)
                stats = db.get_stats()
                status_md = f"**Status:** Running • **Projects:** {stats['active_projects']} • **Pending Updates:** {stats['dirty_projects']}"
                launcher.ui_needs_refresh = False
                launcher.last_ui_update = current_time
                
                return grid_html, status_md, current_time
            
            return gr.update(), gr.update(), last_check_time
        
        # Hidden button for periodic refresh
        refresh_trigger = gr.Button("Auto Refresh", visible=False)
        refresh_trigger.click(
            check_for_updates,
            inputs=[auto_refresh_state],
            outputs=[projects_display, status_display, auto_refresh_state]
        )
        
        # Add JavaScript for periodic refresh (every 15 seconds)
        app.load(
            None,
            None,
            None,
            js="""
            () => {
                setInterval(() => {
                    const refreshBtn = document.querySelector('button[aria-label="Auto Refresh"]') || 
                                     document.querySelector('button:contains("Auto Refresh")');
                    if (refreshBtn && refreshBtn.style.display === 'none') {
                        refreshBtn.click();
                    }
                }, 15000);  // 15 second intervals
                return {};
            }
            """
        )
    
    return app

def find_available_port(start_port=7870, end_port=7890, exclude_ports=None):
    """Find an available port in the specified range, excluding certain ports"""
    import socket
    
    if exclude_ports is None:
        exclude_ports = []
    
    print(f"🚀 [TERMINAL] Searching for available port in range {start_port}-{end_port}, excluding {exclude_ports}")
    
    for port in range(start_port, end_port + 1):
        if port in exclude_ports:
            print(f"🚀 [TERMINAL] Port {port} excluded, skipping...")
            continue
            
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                print(f"🚀 [TERMINAL] Found available port: {port}")
                return port
        except OSError:
            print(f"🚀 [TERMINAL] Port {port} is in use, trying next...")
    
    print(f"🚀 [TERMINAL] No available ports found in range {start_port}-{end_port}")
    return None

if __name__ == "__main__":
    print("🚀 [TERMINAL] =================================")
    print("🚀 [TERMINAL] Starting Persistent AI Project Launcher...")
    print("🚀 [TERMINAL] =================================")
    
    logger.info("Starting Persistent AI Project Launcher...")
    
    try:
        # Find port for API server first
        print("🚀 [TERMINAL] Finding available port for Launch API Server...")
        api_port = find_available_port(start_port=7871, end_port=7890)
        if api_port is None:
            print("❌ No available ports found for API server in range 7871-7890")
            print("🚀 [TERMINAL] Please check if other services are using these ports")
            print("🚀 [TERMINAL] You can check with: lsof -i :7871-7890")
            exit(1)
        
        print("🚀 [TERMINAL] Initializing application...")
        app = main(api_port=api_port)  # Pass API port to main
        print("🚀 [TERMINAL] Application initialized successfully")
        
        # Find available port for Gradio (excluding API server port)
        print("🚀 [TERMINAL] Finding available port for Gradio...")
        gradio_port = find_available_port(start_port=7870, end_port=7890, exclude_ports=[api_port])
        if gradio_port is None:
            print("❌ No available ports found for Gradio in range 7870-7890")
            print("🚀 [TERMINAL] Please check if other services are using these ports")
            print("🚀 [TERMINAL] You can check with: lsof -i :7870-7890")
            exit(1)
        
        print("🚀 [TERMINAL] =================================")
        print("🚀 Persistent AI Project Launcher")
        print(f"📱 Web interface: http://localhost:{gradio_port}")
        print(f"🌐 Launch API: http://localhost:{api_port}")
        print("💾 Using persistent database for project tracking")
        print("🔄 Background scanning enabled")
        print("⏰ Auto-refresh every 15 seconds")
        print("🔍 Real-time search and filtering")
        print("🚀 [TERMINAL] =================================")
        print(f"🚀 [TERMINAL] Starting Gradio server on port {gradio_port}...")
        
        logger.info(f"Starting Gradio server on port {gradio_port}")
        app.launch(share=False, server_name="0.0.0.0", server_port=gradio_port)
        
    except KeyboardInterrupt:
        print("\n🚀 [TERMINAL] Launcher stopped by user")
        logger.info("Launcher stopped by user")
    except Exception as e:
        print(f"🚀 [TERMINAL] FATAL ERROR: {str(e)}")
        logger.error(f"Fatal error during startup: {str(e)}")
        import traceback
        print(f"🚀 [TERMINAL] Traceback: {traceback.format_exc()}")
        exit(1) 