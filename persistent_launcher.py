#!/usr/bin/env python3

import gradio as gr
import json
import time
import threading
from pathlib import Path
from typing import Dict, List
from datetime import datetime

from project_database import db
from background_scanner import get_scanner
from environment_detector import EnvironmentDetector
from logger import logger
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
    
    def create_project_card(self, project: Dict, index: int) -> str:
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
        
        # Description handling
        description = project.get('description', project.get('tooltip', 'AI/ML Project'))
        if not description or description == 'No description available':
            description = project.get('tooltip', f"AI project: {project['name']}")
        
        # Create unique IDs for this card
        card_id = f"card_{index}"
        desc_id = f"desc_{index}"
        btn_id = f"btn_{index}"
        launch_id = f"launch_{index}"
        
        # Escape project path for JavaScript - avoid backslashes in f-strings
        project_path_safe = project['path'].replace('\\', '/').replace("'", "&apos;")
        project_name_safe = project['name'].replace("'", "&apos;")
        
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
                            {project['name']}
                        </h3>
                        <button id="{launch_id}" onclick="launchProject('{project_name_safe}', '{project_path_safe}')" style="
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
                        " onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 4px 8px rgba(0,123,255,0.4)'"
                           onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 4px rgba(0,123,255,0.3)'">
                            🚀 Launch
                        </button>
                    </div>
                    <div style="margin-bottom: 8px;">
                        {' '.join(status_badges)}
                    </div>
                    <div id="{desc_id}" style="
                        font-size: 12px; color: #6c757d; margin: 0 0 8px 0; 
                        line-height: 1.4;
                    ">
                        <div id="{desc_id}_text" style="
                            overflow: hidden;
                            display: -webkit-box;
                            -webkit-line-clamp: 3;
                            -webkit-box-orient: vertical;
                            line-height: 1.4;
                        ">
                            {description}
                        </div>
                        <button id="{btn_id}" onclick="toggleDesc('{desc_id}')" style="
                            background: none; 
                            border: none; 
                            color: #007bff; 
                            cursor: pointer; 
                            font-size: 11px; 
                            text-decoration: underline; 
                            padding: 0; 
                            margin-top: 4px;
                            display: {'block' if len(description) > 150 else 'none'};
                        ">Show more</button>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #868e96;">
                        <span>🐍 {env_type} • 📝 {main_script}</span>
                        <span>Last: {time_str}</span>
                    </div>
                </div>
            </div>
        </div>
        """
    
    def create_projects_grid(self, projects: List[Dict]) -> str:
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
            grid_html += self.create_project_card(project, i)
        
        grid_html += "</div>"
        
        # Add JavaScript functions for interactivity  
        grid_html += """
        <script>
        // Global launch counter for tracking
        window.launchCounter = 0;
        
        function launchProject(projectName, projectPath) {
            window.launchCounter++;
            const launchId = window.launchCounter;
            
            console.log(`[${launchId}] Launching: ${projectName}`);
            
            // Show immediate feedback
            const outputElement = document.getElementById('launch_output');
            if (outputElement) {
                outputElement.value = `🚀 Launching ${projectName}...`;
            }
            
            // Trigger instant launch via hidden input
            const launchInput = document.getElementById('instant_launch_data');
            if (launchInput) {
                const launchData = JSON.stringify({
                    project_name: projectName.replace(/&apos;/g, "'"),
                    project_path: projectPath.replace(/&apos;/g, "'"),
                    launch_id: launchId
                });
                
                launchInput.value = launchData;
                launchInput.dispatchEvent(new Event('input', { bubbles: true }));
            }
            
            return false; // Prevent any default behavior
        }
        
        function toggleDesc(descId) {
            const textDiv = document.getElementById(descId + '_text');
            const btnId = descId.replace('desc_', 'btn_');
            const button = document.getElementById(btnId);
            
            if (textDiv && button) {
                if (textDiv.style.webkitLineClamp === 'none') {
                    // Show truncated
                    textDiv.style.webkitLineClamp = '3';
                    button.textContent = 'Show more';
                } else {
                    // Show full
                    textDiv.style.webkitLineClamp = 'none';
                    button.textContent = 'Show less';
                }
            }
        }
        </script>
        """
        
        return grid_html
    
    def launch_project(self, project_path: str, project_name: str) -> str:
        """Launch a project with its detected environment"""
        try:
            env_detector = EnvironmentDetector()
            env_info = env_detector.detect_environment(project_path)
            
            logger.launch_attempt(project_name, project_path, env_info['type'])
            
            if env_info['type'] == 'none':
                error_msg = f"No Python environment detected for {project_name}"
                logger.launch_error(project_name, error_msg)
                return f"❌ {error_msg}"
            
            # Find main script
            main_scripts = ['app.py', 'main.py', 'run.py', 'start.py', 'launch.py', 'webui.py']
            script_path = None
            
            for script in main_scripts:
                potential_path = Path(project_path) / script
                if potential_path.exists():
                    script_path = potential_path
                    break
            
            if not script_path:
                # Try to find any Python file that might be the main one
                py_files = list(Path(project_path).glob('*.py'))
                if py_files:
                    script_path = py_files[0]
                else:
                    error_msg = f"No Python script found in {project_name}"
                    logger.launch_error(project_name, error_msg)
                    return f"❌ {error_msg}"
            
            # Launch command
            script_name = script_path.name
            project_path_quoted = f'"{project_path}"'
            
            if env_info['type'] == 'conda':
                env_name = env_info.get('name', 'base')
                cmd = f'gnome-terminal --title="{project_name}" -- bash -c "cd {project_path_quoted} && conda activate {env_name} && python3 {script_name}; exec bash"'
            elif env_info['type'] == 'venv':
                activate_path = env_info.get('activate_path', '')
                activate_path_quoted = f'"{activate_path}"'
                cmd = f'gnome-terminal --title="{project_name}" -- bash -c "cd {project_path_quoted} && source {activate_path_quoted} && python3 {script_name}; exec bash"'
            elif env_info['type'] == 'poetry':
                cmd = f'gnome-terminal --title="{project_name}" -- bash -c "cd {project_path_quoted} && poetry run python3 {script_name}; exec bash"'
            elif env_info['type'] == 'pipenv':
                cmd = f'gnome-terminal --title="{project_name}" -- bash -c "cd {project_path_quoted} && pipenv run python3 {script_name}; exec bash"'
            else:
                cmd = f'gnome-terminal --title="{project_name}" -- bash -c "cd {project_path_quoted} && python3 {script_name}; exec bash"'
            
            subprocess.Popen(cmd, shell=True)
            logger.launch_success(project_name)
            return f"✅ Launched {project_name} (Environment: {env_info['type']})"
            
        except Exception as e:
            error_msg = str(e)
            logger.launch_error(project_name, error_msg)
            return f"❌ Error launching project: {error_msg}"

    def launch_project_background(self, project_path: str, project_name: str, launch_id: int = 0) -> str:
        """Launch a project in the background without blocking the UI"""
        def run_launch():
            try:
                result = self.launch_project(project_path, project_name)
                logger.info(f"[{launch_id}] Background launch completed: {project_name}")
                return result
            except Exception as e:
                error_msg = f"❌ Error launching {project_name}: {str(e)}"
                logger.error(f"[{launch_id}] Background launch failed: {error_msg}")
                return error_msg
        
        # Start the launch in a background thread
        thread = threading.Thread(target=run_launch, daemon=True)
        thread.start()
        
        return f"✅ {project_name} is starting... (Background launch #{launch_id})"

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

def main():
    """Main application entry point"""
    config = load_config()
    launcher = PersistentLauncher(config)
    
    # Initialize the launcher
    launcher.initialize()
    
    # Get initial stats
    stats = db.get_stats()
    
    with gr.Blocks(title="🚀 Persistent AI Launcher", theme=gr.themes.Soft()) as app:
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
        projects_display = gr.HTML(launcher.create_projects_grid(launcher.current_projects))
        
        # Launch output for showing launch results
        with gr.Row():
            launch_output = gr.Textbox(label="Launch Output", interactive=False, elem_id="launch_output")
            project_details = gr.Markdown("Click on a project name to see details")
        
        # Single hidden input for instant launches
        with gr.Row(visible=False):
            instant_launch_input = gr.Textbox(elem_id="instant_launch_data")
        
        # Advanced controls
        with gr.Accordion("🛠️ Advanced Controls", open=False):
            with gr.Row():
                view_logs_btn = gr.Button("View Scan History")
                cleanup_btn = gr.Button("Cleanup Old Data")
            
            scan_history = gr.Textbox(label="Recent Scan Sessions", lines=5, interactive=False)
        
        # Event handlers
        def refresh_display():
            launcher.load_projects_from_db()
            grid_html = launcher.create_projects_grid(launcher.current_projects)
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
        
        def handle_instant_launch(launch_data_json):
            """Handle instant project launches from the UI"""
            if not launch_data_json:
                return "No launch data"
                
            try:
                import json
                launch_data = json.loads(launch_data_json)
                project_name = launch_data.get('project_name', '')
                project_path = launch_data.get('project_path', '')
                launch_id = launch_data.get('launch_id', 0)
                
                if not project_name or not project_path:
                    return "❌ Invalid launch data"
                
                # Launch in background immediately
                result = launcher.launch_project_background(project_path, project_name, launch_id)
                logger.info(f"[{launch_id}] Instant launch triggered: {project_name}")
                return result
                
            except Exception as e:
                error_msg = f"❌ Launch error: {str(e)}"
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
        
        # Handle instant launches
        instant_launch_input.change(
            handle_instant_launch,
            inputs=[instant_launch_input],
            outputs=[launch_output]
        )
        
        # Auto-refresh using periodic check - compatible with Gradio 3.41.2
        auto_refresh_state = gr.State(time.time())
        
        def check_for_updates(last_check_time):
            """Periodic check for UI updates"""
            current_time = time.time()
            
            # Only refresh if needed and it's been at least 10 seconds
            if (launcher.ui_needs_refresh and (current_time - last_check_time > 10)) or (current_time - launcher.last_ui_update > 60):
                grid_html = launcher.create_projects_grid(launcher.current_projects)
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

def find_available_port(start_port=7862, max_port=7872):
    """Find an available port in the given range"""
    import socket
    for port in range(start_port, max_port + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    return None

if __name__ == "__main__":
    logger.info("Starting Persistent AI Project Launcher...")
    app = main()
    
    # Find available port
    port = find_available_port()
    if port is None:
        print("❌ No available ports found in range 7862-7872")
        exit(1)
    
    print("🚀 Persistent AI Project Launcher")
    print(f"📱 Web interface: http://localhost:{port}")
    print("💾 Using persistent database for project tracking")
    print("🔄 Background scanning enabled")
    print("⏰ Auto-refresh every 15 seconds")
    app.launch(share=False, server_name="0.0.0.0", server_port=port) 