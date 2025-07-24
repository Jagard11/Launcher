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
            return f'<div style="color: #e8eaed !important; line-height: 1.4;">{description}</div>'
        
        # Create truncated preview (first ~150 characters, cut at word boundary)
        truncated = description[:TRUNCATE_LENGTH]
        # Find the last space to avoid cutting words
        last_space = truncated.rfind(' ')
        if last_space > TRUNCATE_LENGTH * 0.8:  # Only cut at word boundary if it's not too short
            truncated = truncated[:last_space]
        
        preview_text = truncated.strip() + "..."
        
        return f"""
        <details style="color: #e8eaed !important; line-height: 1.4; margin: 0;">
            <summary style="
                cursor: pointer;
                color: #e8eaed !important;
                font-weight: normal;
                list-style: none;
                outline: none;
                user-select: none;
                padding: 2px 0;
                margin: 0;
                position: relative;
                display: block;
            ">
                <span style="color: #e8eaed !important;">{preview_text}</span>
                <span style="
                    color: #64b5f6 !important;
                    font-size: 11px;
                    text-decoration: underline;
                    margin-left: 8px;
                    font-weight: normal;
                "> ▼ Show full description</span>
            </summary>
            <div style="
                color: #e8eaed !important;
                margin-top: 6px;
                line-height: 1.4;
                padding: 8px 0;
                border-top: 1px solid #3c4043;
                background: #252a3a;
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
        
        # Check if custom launcher exists
        project_name = project.get('name', 'Unknown')
        safe_name = "".join(c for c in project_name if c.isalnum() or c in ('-', '_')).strip()
        custom_launcher_path = Path("custom_launchers") / f"{safe_name}.sh"
        has_custom_launcher = custom_launcher_path.exists()
        
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
        
        # Status badges - dark mode
        status_badges = []
        if dirty_flag:
            status_badges.append('<span style="background: #f44336; color: #e8eaed; padding: 3px 8px; border-radius: 6px; font-size: 10px; font-weight: 500;">NEEDS UPDATE</span>')
        else:
            status_badges.append('<span style="background: #4caf50; color: #0f1419; padding: 3px 8px; border-radius: 6px; font-size: 10px; font-weight: 500;">UP TO DATE</span>')
        
        if project.get('is_git', False):
            status_badges.append('<span style="background: #64b5f6; color: #0f1419; padding: 3px 8px; border-radius: 6px; font-size: 10px; font-weight: 500;">GIT</span>')
        
        # Add custom launcher status badge
        if has_custom_launcher:
            status_badges.append('<span style="background: #4caf50; color: #0f1419; padding: 3px 8px; border-radius: 6px; font-size: 10px; font-weight: 500;">✅ LAUNCHER</span>')
        else:
            status_badges.append('<span style="background: #f44336; color: #e8eaed; padding: 3px 8px; border-radius: 6px; font-size: 10px; font-weight: 500;">❌ NO LAUNCHER</span>')
        
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

        # Get favorite and hidden status
        is_favorite = bool(project.get('is_favorite', False))
        is_hidden = bool(project.get('is_hidden', False))
        
        # Dark mode styling based on custom launcher availability
        if has_custom_launcher:
            card_border = "1px solid #3c4043"
            card_background = "linear-gradient(145deg, #1a1f2e, #252a3a)"
            card_shadow = "0 2px 8px rgba(0,0,0,0.3)"
        else:
            # Red highlighting for missing launcher
            card_border = "2px solid #f44336"
            card_background = "linear-gradient(145deg, #2d1b1b, #3d2525)"
            card_shadow = "0 2px 12px rgba(244,67,54,0.4)"

        return f"""
        <div class="project-card" id="{card_id}" style="
            border: {card_border}; 
            border-radius: 12px; 
            padding: 16px; 
            margin: 8px;
            background: {card_background};
            box-shadow: {card_shadow};
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
                        <h3 style="margin: 0; font-size: 16px; color: #e8eaed; font-weight: 600; flex: 1;">
                            {str(project.get('name', 'Unknown Project'))}
                        </h3>
                        <div style="display: flex; gap: 6px; margin-left: 12px;">
                            <button onclick="toggleFavorite('{project_path_safe}')" style="
                                background: {'#ff9800' if is_favorite else '#5f6368'};
                                color: {'#0f1419' if is_favorite else '#e8eaed'}; 
                                border: 1px solid {'#ff9800' if is_favorite else '#3c4043'}; 
                                padding: 6px 10px; 
                                border-radius: 8px; 
                                cursor: pointer; 
                                font-size: 12px;
                                font-weight: 600;
                                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                                transition: all 0.2s ease;
                                text-decoration: none;
                                display: inline-block;
                                min-width: 32px;
                            " onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.4)'"
                               onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.3)'"
                               title="{'Remove from favorites' if is_favorite else 'Add to favorites'}">
                                ⭐
                            </button>
                            <button onclick="toggleHidden('{project_path_safe}')" style="
                                background: {'#f44336' if is_hidden else '#5f6368'};
                                color: {'#e8eaed' if is_hidden else '#e8eaed'}; 
                                border: 1px solid {'#f44336' if is_hidden else '#3c4043'}; 
                                padding: 6px 10px; 
                                border-radius: 8px; 
                                cursor: pointer; 
                                font-size: 12px;
                                font-weight: 600;
                                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                                transition: all 0.2s ease;
                                text-decoration: none;
                                display: inline-block;
                                min-width: 32px;
                            " onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.4)'"
                               onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.3)'"
                               title="{'Show project' if is_hidden else 'Hide project'}">
                                👻
                            </button>
                            <a href="http://localhost:{api_port}/launch?project_id={index}" 
                               target="_blank" 
                               style="
                                background: linear-gradient(135deg, #64b5f6, #42a5f5);
                                color: #0f1419; 
                                border: 1px solid #64b5f6; 
                                padding: 6px 12px; 
                                border-radius: 8px; 
                                cursor: pointer; 
                                font-size: 11px;
                                font-weight: 600;
                                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                                transition: all 0.2s ease;
                                text-decoration: none;
                                display: inline-block;
                            " onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 4px 12px rgba(100,181,246,0.4)'"
                               onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.3)'">
                                🚀 Launch
                            </a>
                        </div>
                    </div>
                    <div style="margin-bottom: 8px;">
                        {' '.join(status_badges)}
                    </div>
                    <div style="
                        font-size: 12px; color: #e8eaed; margin: 0 0 8px 0; 
                        line-height: 1.4;
                    ">
                        {self._create_expandable_description(description)}
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #5f6368;">
                        <span>🐍 {env_type} • 📝 {main_script}</span>
                        <span>Last: {time_str}</span>
                    </div>
                </div>
            </div>
        </div>
        """
    
    def create_projects_grid(self, projects: List[Dict], api_port: int = 7871) -> str:
        """Create responsive grid of project cards with favorites and hidden sections"""
        if not projects:
            return """
            <div style="text-align: center; padding: 40px; color: #9aa0a6;">
                <h3 style="color: #e8eaed;">No projects found</h3>
                <p>The background scanner will automatically discover projects in your configured directories.</p>
            </div>
            """
        
        # Separate projects into categories
        favorites = []
        visible = []
        hidden = []
        
        for i, project in enumerate(projects):
            if project.get('is_favorite', False):
                favorites.append((project, i))
            elif project.get('is_hidden', False):
                hidden.append((project, i))
            else:
                visible.append((project, i))
        
        grid_html = ""
        
        # Favorites section (shown only if there are favorites)
        if favorites:
            grid_html += """
            <div style="margin-bottom: 20px;">
                <h3 style="color: #ff9800; margin: 0 0 12px 16px; font-size: 18px; font-weight: 600; display: flex; align-items: center;">
                    ⭐ Favorites
                </h3>
                <div style="
                    display: grid; 
                    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); 
                    gap: 16px; 
                    padding: 0 16px;
                    border-left: 4px solid #ff9800;
                    margin-left: 16px;
                    padding-left: 20px;
                ">
            """
            
            for project, index in favorites:
                grid_html += self.create_project_card(project, index, api_port)
            
            grid_html += "</div></div>"
        
        # Regular projects section
        if visible:
            section_title = "All Projects" if not favorites else "Projects"
            grid_html += f"""
            <div style="margin-bottom: 20px;">
                <h3 style="color: #e8eaed; margin: 0 0 12px 16px; font-size: 18px; font-weight: 600;">
                    📋 {section_title}
                </h3>
                <div style="
                    display: grid; 
                    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); 
                    gap: 16px; 
                    padding: 0 16px;
                ">
            """
            
            for project, index in visible:
                grid_html += self.create_project_card(project, index, api_port)
            
            grid_html += "</div></div>"
        
        # Hidden projects section (expandable, shown only if there are hidden projects)
        if hidden:
            grid_html += f"""
            <div style="margin-top: 20px;">
                <div style="margin: 0 16px;">
                    <button onclick="toggleHiddenSection()" style="
                        background: #5f6368;
                        color: #e8eaed;
                        border: 1px solid #3c4043;
                        padding: 8px 16px;
                        border-radius: 8px;
                        cursor: pointer;
                        font-size: 14px;
                        font-weight: 600;
                        margin-bottom: 12px;
                        transition: all 0.2s ease;
                    " onmouseover="this.style.background='#2d3448'; this.style.borderColor='#5f6368'"
                       onmouseout="this.style.background='#5f6368'; this.style.borderColor='#3c4043'">
                        👻 Hidden Projects ({len(hidden)}) <span id="hidden-toggle-arrow">▼</span>
                    </button>
                </div>
                <div id="hidden-projects-section" style="
                    display: none;
                    border-left: 4px solid #5f6368;
                    margin-left: 16px;
                    padding-left: 20px;
                ">
                    <div style="
                        display: grid; 
                        grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); 
                        gap: 16px; 
                        padding: 0 16px;
                    ">
            """
            
            for project, index in hidden:
                grid_html += self.create_project_card(project, index, api_port)
            
            grid_html += """
                    </div>
                </div>
            </div>
            """
        
        # Add JavaScript for hidden section toggle and favorite/hidden buttons
        grid_html += f"""
        <script>
        // Make API port available to JavaScript functions
        const api_port = {api_port};
        
        function toggleHiddenSection() {{
            const section = document.getElementById('hidden-projects-section');
            const arrow = document.getElementById('hidden-toggle-arrow');
            
            if (section.style.display === 'none') {{
                section.style.display = 'block';
                arrow.textContent = '▲';
            }} else {{
                section.style.display = 'none';
                arrow.textContent = '▼';
            }}
        }}
        
                 function toggleFavorite(projectPath) {{
             console.log('🌟 [JS] Toggle favorite for:', projectPath);
             
             // Call API to toggle favorite status
             fetch(`http://localhost:${api_port}/api/toggle-favorite`, {{
                 method: 'POST',
                 headers: {{
                     'Content-Type': 'application/json',
                 }},
                 body: JSON.stringify({{
                     project_path: projectPath
                 }})
             }})
             .then(response => response.json())
             .then(data => {{
                 console.log('🌟 [JS] API response:', data);
                 if (data.success) {{
                     console.log('🌟 [JS] Successfully toggled favorite, triggering refresh...');
                     
                     // Trigger the hidden refresh button
                     const hiddenRefreshBtn = document.querySelector('#hidden_refresh_trigger');
                     if (hiddenRefreshBtn) {{
                         hiddenRefreshBtn.click();
                         console.log('🌟 [JS] Triggered hidden refresh');
                     }} else {{
                         console.log('🌟 [JS] Hidden refresh button not found, using page reload');
                         setTimeout(() => {{
                             window.location.reload();
                         }}, 500);
                     }}
                 }} else {{
                     console.error('Failed to toggle favorite:', data.error);
                     alert('Failed to toggle favorite: ' + data.error);
                 }}
             }})
             .catch(error => {{
                 console.error('Error toggling favorite:', error);
                 alert('Error toggling favorite: ' + error);
             }});
         }}
         
         function toggleHidden(projectPath) {{
             console.log('👻 [JS] Toggle hidden for:', projectPath);
             
             // Call API to toggle hidden status
             fetch(`http://localhost:${api_port}/api/toggle-hidden`, {{
                 method: 'POST',
                 headers: {{
                     'Content-Type': 'application/json',
                 }},
                 body: JSON.stringify({{
                     project_path: projectPath
                 }})
             }})
             .then(response => response.json())
             .then(data => {{
                 console.log('👻 [JS] API response:', data);
                 if (data.success) {{
                     console.log('👻 [JS] Successfully toggled hidden, triggering refresh...');
                     
                     // Trigger the hidden refresh button
                     const hiddenRefreshBtn = document.querySelector('#hidden_refresh_trigger');
                     if (hiddenRefreshBtn) {{
                         hiddenRefreshBtn.click();
                         console.log('👻 [JS] Triggered hidden refresh');
                     }} else {{
                         console.log('👻 [JS] Hidden refresh button not found, using page reload');
                         setTimeout(() => {{
                             window.location.reload();
                         }}, 500);
                     }}
                 }} else {{
                     console.error('Failed to toggle hidden:', data.error);
                     alert('Failed to toggle hidden: ' + data.error);
                 }}
             }})
             .catch(error => {{
                 console.error('Error toggling hidden:', error);
                 alert('Error toggling hidden: ' + error);
             }});
         }}
        
        // Make functions globally available
        window.toggleHiddenSection = toggleHiddenSection;
        window.toggleFavorite = toggleFavorite;
        window.toggleHidden = toggleHidden;
        </script>
        """
        
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

    def get_project_details_with_launch_info(self, project_path: str) -> Dict:
        """Get detailed project information including launch method analysis"""
        try:
            from qwen_launch_analyzer import QwenLaunchAnalyzer
            
            # Get project from database
            project_data = db.get_project_by_path(project_path)
            if not project_data:
                return {"error": "Project not found in database"}
            
            # Get AI analysis
            analyzer = QwenLaunchAnalyzer()
            launch_info = analyzer.get_launch_alternatives_for_ui(project_path, project_data['name'])
            
            # Combine all information
            return {
                'project': project_data,
                'launch_info': launch_info,
                'project_path': project_path
            }
        except Exception as e:
            logger.error(f"Error getting project details: {e}")
            return {"error": str(e)}
    
    def create_launch_details_modal(self, project_data: Dict) -> str:
        """Create a detailed launch method display with editing capabilities"""
        if 'error' in project_data:
            return f"<div class='error'>Error: {project_data['error']}</div>"
        
        project = project_data['project']
        launch_info = project_data['launch_info']
        project_path = project_data['project_path']
        
        # Get current launch command from database
        current_command = project.get('launch_command', 'Not determined')
        confidence = launch_info.get('confidence', 0.0)
        needs_input = launch_info.get('needs_user_input', False)
        alternatives = launch_info.get('alternatives', [])
        custom_launcher_path = launch_info.get('custom_launcher_path', '')
        
        # Create the modal content
        modal_html = f"""
        <div style="
            background: white; 
            border: 2px solid #007bff; 
            border-radius: 12px; 
            padding: 20px; 
            margin: 10px 0;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        ">
            <h3 style="color: #2c3e50; margin-top: 0;">🔧 Launch Method for {project['name']}</h3>
            
            <div style="margin: 15px 0; padding: 12px; background: #f8f9fa; border-radius: 8px;">
                <strong>Current Launch Command:</strong><br>
                <code style="background: #e9ecef; padding: 4px 8px; border-radius: 4px; color: #495057;">
                    {current_command}
                </code>
            </div>
            
            <div style="margin: 15px 0;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <strong>AI Confidence:</strong>
                    <div style="
                        background: {'#d4edda' if confidence > 0.7 else '#fff3cd' if confidence > 0.4 else '#f8d7da'};
                        color: {'#155724' if confidence > 0.7 else '#856404' if confidence > 0.4 else '#721c24'};
                        padding: 4px 12px;
                        border-radius: 15px;
                        font-size: 12px;
                        font-weight: bold;
                    ">
                        {confidence:.1%} {'✅' if confidence > 0.7 else '⚠️' if confidence > 0.4 else '❌'}
                    </div>
                </div>
                <div style="margin-top: 8px; font-size: 14px; color: #6c757d;">
                    Project Type: {launch_info.get('project_type', 'Unknown')}
                </div>
            </div>
        """
        
        # Show alternatives if available
        if alternatives:
            modal_html += """
            <div style="margin: 15px 0;">
                <strong>Alternative Launch Methods:</strong>
                <ul style="margin-top: 8px;">
            """
            for alt in alternatives:
                alt_confidence = alt.get('confidence', 0.0)
                modal_html += f"""
                <li style="margin: 5px 0;">
                    <code style="background: #e9ecef; padding: 2px 6px; border-radius: 3px;">
                        {alt.get('command', 'N/A')}
                    </code>
                    <span style="color: #6c757d; font-size: 12px;">
                        ({alt_confidence:.1%} confidence)
                    </span>
                    <br>
                    <small style="color: #868e96;">{alt.get('reasoning', '')}</small>
                </li>
                """
            modal_html += "</ul></div>"
        
        # Show uncertainty notes if available
        uncertainty = launch_info.get('uncertainty_notes', '')
        if uncertainty:
            modal_html += f"""
            <div style="
                margin: 15px 0; 
                padding: 12px; 
                background: #fff3cd; 
                border: 1px solid #ffeaa7; 
                border-radius: 8px;
                color: #856404;
            ">
                <strong>⚠️ AI Notes:</strong><br>
                {uncertainty}
            </div>
            """
        
        # Show custom launcher info if available
        if custom_launcher_path:
            modal_html += f"""
            <div style="
                margin: 15px 0; 
                padding: 12px; 
                background: #d1ecf1; 
                border: 1px solid #bee5eb; 
                border-radius: 8px;
                color: #0c5460;
            ">
                <strong>🛠️ Custom Launcher Created:</strong><br>
                Edit the file: <code>{custom_launcher_path}</code><br>
                <small>This file contains suggested launch commands that you can modify.</small>
            </div>
            """
        
        # Instructions for manual editing
        modal_html += f"""
        <div style="
            margin: 20px 0; 
            padding: 15px; 
            background: #e7f3ff; 
            border: 1px solid #b3d7ff; 
            border-radius: 8px;
        ">
            <h4 style="color: #004085; margin-top: 0;">📝 Manual Override Options:</h4>
            
            <div style="margin: 10px 0;">
                <button onclick="reanalyzeProject('{project_path}')" style="
                    background: linear-gradient(135deg, #28a745, #20c997);
                    color: white; 
                    border: none; 
                    padding: 8px 16px; 
                    border-radius: 20px; 
                    cursor: pointer; 
                    font-size: 13px;
                    font-weight: 600;
                    margin-right: 10px;
                    box-shadow: 0 2px 4px rgba(40,167,69,0.3);
                ">
                    🔄 Re-analyze with New AI
                </button>
                <small style="color: #495057;">Force re-analysis using the latest AI detection system</small>
            </div>
            
            <p style="margin: 8px 0;"><strong>Option 1: Edit Custom Launcher</strong></p>
            <p style="margin: 8px 0; font-size: 14px; color: #495057;">
                Create/edit: <code>custom_launchers/{project['name'].replace(' ', '_').replace('-', '_')}.sh</code>
            </p>
            
            <p style="margin: 8px 0;"><strong>Option 2: Database Override</strong></p>
            <p style="margin: 8px 0; font-size: 14px; color: #495057;">
                Use the Database tab to directly edit the launch command in the database.
            </p>
            
            <p style="margin: 8px 0;"><strong>Option 3: Project-Level Script</strong></p>
            <p style="margin: 8px 0; font-size: 14px; color: #495057;">
                Create a <code>start.sh</code> or <code>launch.sh</code> script in the project directory.
            </p>
        </div>
        """
        
        # Analysis details for debugging
        if launch_info.get('analysis_notes'):
            modal_html += f"""
            <details style="margin: 15px 0;">
                <summary style="cursor: pointer; color: #007bff; font-weight: bold;">
                    🔍 AI Analysis Details
                </summary>
                <div style="margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 6px; font-size: 13px; color: #495057;">
                    {launch_info['analysis_notes']}
                </div>
            </details>
            """
        
        modal_html += "</div>"
        return modal_html

    def rebuild_launch_commands(self) -> str:
        """Rebuild all launch commands using the new AI detection system"""
        try:
            logger.info("Starting launch command rebuild for all projects...")
            
            # Get all projects from database
            all_projects = db.get_all_projects(active_only=False)
            
            if not all_projects:
                return "❌ No projects found in database"
            
            # Mark all projects as dirty to force re-analysis
            rebuild_count = 0
            for project in all_projects:
                try:
                    # Clear existing launch data and mark as dirty
                    update_data = {
                        'path': project['path'],
                        'dirty_flag': 1,  # Mark as needing re-analysis
                        'launch_command': '',  # Clear old command
                        'launch_confidence': 0.0,  # Reset confidence
                        'launch_notes': 'Marked for rebuild with new AI system',
                        'launch_analysis_method': 'pending_rebuild',
                        'launch_analyzed_at': time.time()
                    }
                    
                    db.upsert_project(update_data)
                    rebuild_count += 1
                    
                except Exception as e:
                    logger.error(f"Error marking project for rebuild: {project.get('name', 'Unknown')} - {e}")
            
            # Trigger the background scanner to process dirty projects
            if self.scanner:
                self.scanner.trigger_dirty_cleanup()
            
            logger.info(f"Marked {rebuild_count} projects for launch command rebuild")
            return f"✅ Marked {rebuild_count} projects for rebuild. Background processing started."
            
        except Exception as e:
            error_msg = f"Error rebuilding launch commands: {str(e)}"
            logger.error(error_msg)
            return f"❌ {error_msg}"
    
    def force_reanalyze_project(self, project_path: str) -> str:
        """Force re-analysis of a specific project's launch method"""
        try:
            from qwen_launch_analyzer import QwenLaunchAnalyzer
            
            # Get project from database
            project_data = db.get_project_by_path(project_path)
            if not project_data:
                return "❌ Project not found in database"
            
            # Run new AI analysis
            analyzer = QwenLaunchAnalyzer()
            env_detector = EnvironmentDetector()
            env_info = env_detector.detect_environment(project_path)
            
            launch_analysis = analyzer.generate_launch_command(
                project_path, 
                project_data['name'], 
                env_info.get('type', 'none'), 
                env_info.get('name', '')
            )
            
            # Update database with new analysis
            update_data = {
                'path': project_path,
                'launch_command': launch_analysis.get('launch_command', ''),
                'launch_type': launch_analysis.get('launch_type', 'unknown'),
                'launch_working_directory': launch_analysis.get('working_directory', '.'),
                'launch_args': launch_analysis.get('requires_args', ''),
                'launch_confidence': launch_analysis.get('confidence', 0.0),
                'launch_notes': launch_analysis.get('notes', ''),
                'launch_analysis_method': launch_analysis.get('analysis_method', 'forced_reanalysis'),
                'main_script': launch_analysis.get('main_script', ''),
                'dirty_flag': 0,  # Mark as clean since we just analyzed it
                'launch_analyzed_at': time.time()
            }
            
            db.upsert_project(update_data)
            
            # Reload projects to reflect changes
            self.load_projects_from_db()
            self.ui_needs_refresh = True
            
            logger.info(f"Force re-analyzed project: {project_data['name']}")
            return f"✅ Re-analyzed {project_data['name']}: {launch_analysis.get('launch_command', 'No command')}"
            
        except Exception as e:
            error_msg = f"Error re-analyzing project: {str(e)}"
            logger.error(error_msg)
            return f"❌ {error_msg}"

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
        
        # Sticky search bar with keyboard shortcuts and launch functions
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
        
        // Launch project function for project cards
        function launchProject(projectName, projectPath) {
            console.log('🚀 [JS] Launch request:', projectName, 'at', projectPath);
            
            // Set hidden inputs
            const nameInput = document.querySelector('#project_name_data input');
            const pathInput = document.querySelector('#project_path_data input');
            const launchBtn = document.querySelector('#launch_trigger');
            
            if (nameInput && pathInput && launchBtn) {
                nameInput.value = projectName;
                nameInput.dispatchEvent(new Event('input'));
                
                pathInput.value = projectPath;
                pathInput.dispatchEvent(new Event('input'));
                
                // Trigger launch after a short delay
                setTimeout(() => {
                    launchBtn.click();
                }, 100);
            } else {
                console.error('🚀 [JS] Could not find required elements');
            }
        }
        
        // View launch details function for project cards
        function viewLaunchDetails(projectPath) {
            console.log('🔧 [JS] View launch details request for:', projectPath);
            
            // Set the project path for details
            const pathInput = document.querySelector('#project_path_for_details input');
            const detailsBtn = document.querySelector('#show_details_trigger');
            
            if (pathInput && detailsBtn) {
                pathInput.value = projectPath;
                pathInput.dispatchEvent(new Event('input'));
                
                // Trigger show details after a short delay
                setTimeout(() => {
                    detailsBtn.click();
                }, 100);
            } else {
                console.error('🔧 [JS] Could not find details elements');
            }
        }
        
        // Re-analyze project function for launch details modal
        function reanalyzeProject(projectPath) {
            console.log('🔄 [JS] Re-analyze request for:', projectPath);
            
            // Set the project path for re-analysis
            const pathInput = document.querySelector('#reanalyze_path_input input');
            
            if (pathInput) {
                pathInput.value = projectPath;
                pathInput.dispatchEvent(new Event('input'));
                
                // Find and click the re-analyze button
                const buttons = document.querySelectorAll('button');
                for (let btn of buttons) {
                    if (btn.textContent.includes('Re-analyze Project')) {
                        setTimeout(() => {
                            btn.click();
                        }, 100);
                        break;
                    }
                }
            } else {
                console.error('🔄 [JS] Could not find re-analyze elements');
            }
        }
        
        // Make functions globally available
        window.launchProject = launchProject;
        window.viewLaunchDetails = viewLaunchDetails;
        window.reanalyzeProject = reanalyzeProject;
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
        
        # Launch Method Details Modal
        with gr.Row():
            launch_details_modal = gr.HTML("", visible=False, elem_id="launch_details_modal")
            close_modal_btn = gr.Button("❌ Close Details", visible=False, elem_id="close_modal_btn")
        
        # Hidden components for launch details
        with gr.Row(visible=False):
            project_path_for_details = gr.Textbox(elem_id="project_path_for_details")
            show_details_trigger = gr.Button("Show Details", elem_id="show_details_trigger")
        
        # Hidden components for instant launches
        with gr.Row(visible=False):
            instant_launch_input = gr.Textbox(elem_id="instant_launch_data")
            project_name_input = gr.Textbox(elem_id="project_name_data")
            project_path_input = gr.Textbox(elem_id="project_path_data")
            launch_trigger = gr.Button("Launch", elem_id="launch_trigger")
        
        # Hidden refresh button for JavaScript to trigger
        with gr.Row(visible=False):
            hidden_refresh_trigger = gr.Button("Hidden Refresh", elem_id="hidden_refresh_trigger")
        
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
                view_logs_btn = gr.Button("📜 View Scan History")
            
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
        
        # Wire up hidden refresh trigger for JavaScript
        hidden_refresh_trigger.click(
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

        def handle_show_launch_details(project_path):
            """Handle showing launch details modal"""
            if not project_path:
                return gr.update(), gr.update(visible=False), gr.update(visible=False)
            
            try:
                project_details_data = launcher.get_project_details_with_launch_info(project_path)
                modal_html = launcher.create_launch_details_modal(project_details_data)
                return modal_html, gr.update(visible=True), gr.update(visible=True)
            except Exception as e:
                error_html = f"<div style='color: red; padding: 20px;'>Error loading launch details: {str(e)}</div>"
                return error_html, gr.update(visible=True), gr.update(visible=True)
        
        def handle_close_modal():
            """Handle closing the launch details modal"""
            return "", gr.update(visible=False), gr.update(visible=False)
        
        # Wire up launch details events
        show_details_trigger.click(
            handle_show_launch_details,
            inputs=[project_path_for_details],
            outputs=[launch_details_modal, launch_details_modal, close_modal_btn]
        )
        
        close_modal_btn.click(
            handle_close_modal,
            outputs=[launch_details_modal, launch_details_modal, close_modal_btn]
        )
        
        # Add project path change handler for details
        project_path_for_details.change(
            lambda x: log_input_change(x, "project_path_for_details"),
            inputs=[project_path_for_details],
            outputs=[]
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