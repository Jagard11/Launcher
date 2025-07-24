#!/usr/bin/env python3

import gradio as gr
import argparse
import sys
import logging 
import json
import time
import threading
import socket
from pathlib import Path
from typing import Dict, List
from datetime import datetime
import platform
import shutil

# Import existing modules
from project_database import db
from database_ui import build_database_ui
from settings_ui import build_settings_ui, config_exists, create_default_config
from background_scanner import get_scanner
from environment_detector import EnvironmentDetector
from logger import logger
from launch_api_server import start_api_server

class UnifiedLauncher:
    def __init__(self, config: dict, verbose: bool = False):
        self.config = config
        self.verbose = verbose
        self.env_detector = EnvironmentDetector()
        self.current_projects = []
        self.scanner = None
        
        # UI state tracking
        self.ui_needs_refresh = False
        self.last_ui_update = time.time()
        
        # Configure logging based on verbose flag
        if verbose:
            # Set the underlying logger to INFO level for verbose output
            logging.getLogger("AILauncher").setLevel(logging.INFO)
            logging.getLogger().setLevel(logging.INFO)
        else:
            # Set to WARNING level for minimal output
            logging.getLogger("AILauncher").setLevel(logging.WARNING)
            logging.getLogger().setLevel(logging.WARNING)
    
    def open_terminal(self, command):
        """Opens a new terminal window and executes the given command - cross-platform"""
        import platform
        import shutil
        import subprocess
        
        os_name = platform.system()
        print(f"🚀 [UNIFIED] Opening terminal on {os_name} with command: {command[:100]}...")
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
                        print(f"🚀 [UNIFIED] Found terminal: {terminal}")
                        break
                
                if not terminal_found:
                    raise OSError("No suitable terminal emulator found. Please install gnome-terminal, konsole, or xterm.")
                
                # Execute command based on terminal type
                if terminal_found == 'gnome-terminal':
                    subprocess.Popen([terminal_found, '--', 'bash', '-c', command])
                elif terminal_found == 'konsole':
                    subprocess.Popen([terminal_found, '-e', 'bash', '-c', command])
                elif terminal_found in ['xfce4-terminal', 'mate-terminal', 'lxterminal']:
                    subprocess.Popen([terminal_found, '-e', f'bash -c "{command}"'])
                elif terminal_found == 'terminator':
                    subprocess.Popen([terminal_found, '-x', 'bash', '-c', command])
                elif terminal_found == 'xterm':
                    subprocess.Popen([terminal_found, '-e', f'bash -c "{command}"'])
                else:
                    # Fallback for any other terminal
                    subprocess.Popen([terminal_found, '-e', f'bash -c "{command}"'])
                    
            elif os_name == "Darwin":  # macOS
                # Uses AppleScript to open Terminal.app and run the command
                subprocess.Popen(['osascript', '-e', f'tell application "Terminal" to do script "{command}"'])
            else:
                raise OSError(f"Unsupported operating system: {os_name}")
                
            print(f"🚀 [UNIFIED] Terminal opened successfully")
            logger.info("Terminal opened successfully")
            return "Terminal launched successfully!"
            
        except Exception as e:
            error_msg = f"Error launching terminal: {str(e)}"
            print(f"🚀 [UNIFIED] ERROR: {error_msg}")
            logger.error(error_msg)
            return error_msg
    
    def initialize(self):
        """Initialize the launcher - load from database and start background scanner"""
        logger.info("Initializing Unified AI Launcher...")
        
        # Load existing projects from database
        self.load_projects_from_db()
        
        # Start background scanner
        self.scanner = get_scanner(self.config, self.on_scanner_update)
        self.scanner.start()
        
        logger.info(f"Launcher initialized with {len(self.current_projects)} projects")
    
    def load_projects_from_db(self):
        """Load projects from database with sort preferences"""
        try:
            # Get sort preferences from config
            sort_by = self.config.get('sort_preference', 'name')
            sort_direction = self.config.get('sort_direction', 'asc')
            
            self.current_projects = db.get_all_projects(active_only=True, sort_by=sort_by, sort_direction=sort_direction)
            logger.info(f"Loaded {len(self.current_projects)} projects from database, sorted by {sort_by} ({sort_direction})")
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
    
    def rebuild_launch_commands(self) -> str:
        """Rebuild all launch commands by marking all projects as dirty for background processing"""
        try:
            from project_database import db
            
            # Get all projects
            all_projects = db.get_all_projects(active_only=False)
            
            if not all_projects:
                return "❌ No projects found in database"
            
            # Mark all projects as dirty for re-analysis
            dirty_count = 0
            for project in all_projects:
                project_path = project.get('path')
                if project_path:
                    # Mark as dirty in database
                    db.mark_project_dirty(project_path)
                    dirty_count += 1
            
            logger.info(f"Marked {dirty_count} projects as dirty for launch command rebuild")
            
            return f"✅ Marked {dirty_count} projects for launch command rebuild. Background scanner will process them shortly."
            
        except Exception as e:
            logger.error(f"Error rebuilding launch commands: {e}")
            return f"❌ Error rebuilding launch commands: {str(e)}"
    
    def force_reanalyze_project(self, project_path: str) -> str:
        """Force re-analysis of a specific project's launch command"""
        try:
            if not project_path or not project_path.strip():
                return "❌ Please provide a valid project path"
            
            project_path = project_path.strip()
            
            # Check if project exists in database
            from project_database import db
            project_data = db.get_project_by_path(project_path)
            
            if not project_data:
                return f"❌ Project not found in database: {project_path}"
            
            # Check if path actually exists
            if not Path(project_path).exists():
                return f"❌ Project path does not exist: {project_path}"
            
            # Use QwenLaunchAnalyzer to re-analyze
            from qwen_launch_analyzer import QwenLaunchAnalyzer
            analyzer = QwenLaunchAnalyzer()
            
            project_name = project_data.get('name', Path(project_path).name)
            env_type = project_data.get('environment_type', 'none')
            env_name = project_data.get('environment_name', '')
            
            # Generate new launch analysis
            launch_analysis = analyzer.generate_launch_command(
                project_path, project_name, env_type, env_name
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
                'launch_analysis_method': launch_analysis.get('analysis_method', 'manual_reanalysis'),
                'launch_analyzed_at': launch_analysis.get('analyzed_at', time.time()),
                'main_script': launch_analysis.get('main_script', ''),
                'dirty_flag': 0,  # Clear dirty flag since we just analyzed
                'last_scanned': time.time()
            }
            
            db.upsert_project(update_data)
            
            # Generate result message
            result_parts = [
                f"✅ Re-analyzed project: {project_name}",
                f"   📁 Path: {project_path}",
                f"   🚀 Launch Command: {launch_analysis.get('launch_command', 'None')}",
                f"   🎯 Confidence: {launch_analysis.get('confidence', 0.0):.1%}",
                f"   📝 Method: {launch_analysis.get('analysis_method', 'unknown')}"
            ]
            
            if launch_analysis.get('custom_launcher_path'):
                result_parts.append(f"   📄 Custom Launcher: {launch_analysis['custom_launcher_path']}")
            
            if launch_analysis.get('notes'):
                result_parts.append(f"   💡 Notes: {launch_analysis['notes']}")
            
            logger.info(f"Re-analyzed project {project_name}: {launch_analysis.get('launch_command')}")
            
            return "\n".join(result_parts)
            
        except Exception as e:
            logger.error(f"Error re-analyzing project {project_path}: {e}")
            return f"❌ Error re-analyzing project: {str(e)}"
    
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
                
            elif event_type == 'projects_missing':
                # Handle missing projects detection
                missing_count = data.get('count', 0)
                missing_projects = data.get('projects', [])
                
                project_names = [p.get('name', 'Unknown') for p in missing_projects]
                logger.warning(f"Scan detected {missing_count} missing project folders: {', '.join(project_names)}")
                
                # Reload projects to ensure UI is in sync (removes inactive projects from view)
                self.load_projects_from_db()
                self.ui_needs_refresh = True
                
            elif event_type == 'launchers_cleaned':
                # Handle custom launcher cleanup
                cleaned_count = data.get('count', 0)
                cleaned_projects = data.get('projects', [])
                
                logger.info(f"Process cleaned up {cleaned_count} custom launchers for removed projects: {', '.join(cleaned_projects)}")
                
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
        project_path = project.get('path', '')
        safe_name = "".join(c for c in project_name if c.isalnum() or c in ('-', '_')).strip()
        custom_launcher_path = Path("custom_launchers") / f"{safe_name}.sh"
        has_custom_launcher = custom_launcher_path.exists()
        
        # Escape variables for safe JavaScript usage
        escaped_name = project_name.replace("'", "\\'").replace('"', '\\"')
        escaped_path = project_path.replace("'", "\\'").replace('"', '\\"')
        
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
                            <button id="launch_btn_{index}" data-project-name="{escaped_name}" data-project-path="{escaped_path}" data-project-index="{index}"
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
                            </button>
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
        
        # Add JavaScript for hidden section toggle and Gradio-native launch handling
        grid_html += f"""
        <script>
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
            console.log('🌟 [JS] Toggle favorite via Gradio for:', projectPath);
            // Placeholder - will be replaced with global implementation
        }}
        
        function toggleHidden(projectPath) {{
            console.log('👻 [JS] Toggle hidden via Gradio for:', projectPath);
            // Placeholder - will be replaced with global implementation
        }}
        
        // Make functions globally available
        window.toggleHiddenSection = toggleHiddenSection;
        </script>
        """
        
        return grid_html
    
    def build_app_list_tab(self, api_port: int):
        """Build the app list tab with existing functionality"""
        # Initialize the launcher
        self.initialize()
        
        # Get initial stats
        stats = db.get_stats()
        
        with gr.Column():
            # Add custom CSS for styling (simplified version)
            gr.HTML("""
            <style>

            .search-input {
                width: 100% !important;
                max-width: none !important;
                margin: 0 !important;
                padding: 6px 12px !important;
                border: 1px solid var(--border-primary) !important;
                border-radius: 6px !important;
                font-size: 14px !important;
                outline: none !important;
                transition: all 0.2s ease !important;
                background: var(--bg-tertiary) !important;
                color: var(--text-primary) !important;
            }
            .search-input:focus {
                border-color: var(--accent-blue) !important;
                box-shadow: 0 0 0 2px rgba(100, 181, 246, 0.2) !important;
                background: var(--bg-hover) !important;
            }
            .search-input::placeholder {
                color: var(--text-muted) !important;
            }
            .search-label {
                color: var(--text-secondary) !important;
                font-weight: 500 !important;
                font-size: 14px !important;
                margin: 0 8px 0 0 !important;
                display: inline-block !important;
                white-space: nowrap !important;
            }
            .search-clear-btn {
                background: var(--bg-tertiary) !important;
                border: 1px solid var(--border-primary) !important;
                border-radius: 6px !important;
                width: 28px !important;
                height: 28px !important;
                padding: 0 !important;
                margin-left: 8px !important;
                color: var(--text-secondary) !important;
                font-size: 12px !important;
                transition: all 0.2s ease !important;
                cursor: pointer !important;
            }
            .search-clear-btn:hover {
                background: var(--accent-red) !important;
                color: var(--text-primary) !important;
                border-color: var(--accent-red) !important;
            }
            .sort-controls-inline {
                display: flex !important;
                align-items: end !important;
                justify-content: flex-end !important;
                gap: 12px !important;
                margin-top: 0 !important;
            }
            .sort-dropdown-inline {
                margin-bottom: 0 !important;
            }
            .sort-dropdown-inline label {
                font-size: 12px !important;
                font-weight: 500 !important;
                color: var(--text-secondary) !important;
                margin-bottom: 4px !important;
                white-space: nowrap !important;
            }
            .sort-dropdown-inline .wrap {
                min-height: 32px !important;
                height: 32px !important;
                margin-bottom: 0 !important;
            }
            .sort-dropdown-inline select, .sort-dropdown-inline .svelte-1gfkn6j {
                min-height: 28px !important;
                height: 28px !important;
                padding: 4px 8px !important;
                font-size: 12px !important;
                border-radius: 4px !important;
            }
            /* Project cards - styled in main launcher */
            </style>
            """)
            
            # Note: Search bar is now fixed at the top - removed from here
            
            # Status and controls - compact and clean
            with gr.Row(elem_classes="status-controls"):
                with gr.Column(scale=4):
                    status_display = gr.Markdown(f"""
📊 **{stats['active_projects']} Projects** • 🔄 **{stats['dirty_projects']} Pending Updates**
                    """)
                
                with gr.Column(scale=2):
                    with gr.Row():
                        manual_scan_btn = gr.Button("🔄 Scan", size="sm")
                        process_dirty_btn = gr.Button("🤖 Process", size="sm")
                        refresh_btn = gr.Button("♻️ Refresh", size="sm")
                
                with gr.Column(scale=3):
                    with gr.Row(elem_classes="sort-controls-inline"):
                        sort_by_dropdown = gr.Dropdown(
                            label="Sort By",
                            choices=[
                                ("Project Name", "name"),
                                ("Directory Path", "directory"), 
                                ("Last Modified", "last_modified"),
                                ("Environment Type", "environment_type"),
                                ("Project Size", "size")
                            ],
                            value=self.config.get('sort_preference', 'name'),
                            scale=2,
                            elem_classes="sort-dropdown-inline"
                        )
                        sort_direction_dropdown = gr.Dropdown(
                            label="Order",
                            choices=[
                                ("A-Z", "asc"),
                                ("Z-A", "desc")
                            ],
                            value=self.config.get('sort_direction', 'asc'),
                            scale=1,
                            elem_classes="sort-dropdown-inline"
                        )
            
            # Projects display
            projects_display = gr.HTML(self.create_projects_grid(self.current_projects, api_port))
            
            # Hidden components for instant launches (styled hidden but DOM accessible)
            with gr.Row(elem_classes="hidden-launch-controls"):
                instant_launch_input = gr.Textbox(elem_id="instant_launch_data", container=False, show_label=False)
                project_name_input = gr.Textbox(elem_id="project_name_data", container=False, show_label=False)
                project_path_input = gr.Textbox(elem_id="project_path_data", container=False, show_label=False)
                launch_trigger = gr.Button("Launch", elem_id="launch_trigger", size="sm")
                
            # Hidden refresh button for JavaScript to trigger automatic refresh
            with gr.Row(visible=False):
                hidden_refresh_trigger = gr.Button("Hidden Refresh", elem_id="hidden_refresh_trigger")
            
            # Event handlers (simplified)
            def handle_search(query):
                filtered_projects = self.filter_projects(query)
                return self.create_projects_grid(filtered_projects, api_port)
            
            def handle_manual_scan():
                try:
                    if self.scanner:
                        self.scanner.trigger_scan()
                    self.load_projects_from_db()
                    stats = db.get_stats()
                    
                    status_parts = [f"**Projects:** {stats['active_projects']}"]
                    if stats['dirty_projects'] > 0:
                        status_parts.append(f"**Pending Updates:** {stats['dirty_projects']}")
                    
                    status_md = f"**Status:** Scan Complete • {' • '.join(status_parts)}"
                    projects_html = self.create_projects_grid(self.current_projects, api_port)
                    return status_md, projects_html
                except Exception as e:
                    return f"**Status:** Scan Error: {str(e)}", gr.update()
            
            def handle_refresh():
                self.load_projects_from_db()
                stats = db.get_stats()
                status_md = f"**Status:** Refreshed • **Projects:** {stats['active_projects']} • **Pending Updates:** {stats['dirty_projects']}"
                projects_html = self.create_projects_grid(self.current_projects, api_port)
                return status_md, projects_html
            
            def clear_search():
                projects_html = self.create_projects_grid(self.current_projects, api_port)
                return "", projects_html
            
            def handle_sort_change(sort_by, sort_direction):
                """Handle changes to sort preferences"""
                try:
                    # Update config in memory
                    self.config['sort_preference'] = sort_by
                    self.config['sort_direction'] = sort_direction
                    
                    # Save config to file
                    from settings_ui import SettingsManager
                    settings_manager = SettingsManager()
                    settings_manager.save_config(self.config)
                    
                    # Reload projects with new sort
                    self.load_projects_from_db()
                    
                    # Update display
                    projects_html = self.create_projects_grid(self.current_projects, api_port)
                    return projects_html
                except Exception as e:
                    logger.error(f"Error changing sort: {e}")
                    return self.create_projects_grid(self.current_projects, api_port)
            
            def handle_launch(project_name, project_path):
                """Launch a project using custom launcher or generate one if needed"""
                try:
                    print(f"\n🚀 [GRADIO-LAUNCH] ===== LAUNCH REQUEST RECEIVED =====")
                    print(f"🚀 [GRADIO-LAUNCH] Function called with:")
                    print(f"🚀 [GRADIO-LAUNCH]   Project: '{project_name}'")
                    print(f"🚀 [GRADIO-LAUNCH]   Path: '{project_path}'")
                    print(f"🚀 [GRADIO-LAUNCH] =====================================")
                    
                    if not project_name or not project_path:
                        print(f"❌ [GRADIO-LAUNCH] Missing required parameters!")
                        return "❌ Missing project name or path"
                    
                    print(f"🚀 [UNIFIED] ===== SMART LAUNCH SYSTEM =====")
                    print(f"🚀 [UNIFIED] Project: {project_name}")
                    print(f"🚀 [UNIFIED] Path: {project_path}")
                    
                    # First, check if a custom launcher exists (highest priority)
                    safe_name = "".join(c for c in project_name if c.isalnum() or c in ('-', '_')).strip()
                    custom_launcher_path = Path("custom_launchers") / f"{safe_name}.sh"
                    
                    if custom_launcher_path.exists():
                        print(f"🚀 [UNIFIED] ✅ Found custom launcher: {custom_launcher_path}")
                        print(f"🚀 [UNIFIED] Using custom launcher script for {project_name}")
                        
                        # Make sure it's executable
                        import os
                        try:
                            os.chmod(custom_launcher_path, 0o755)
                        except:
                            pass  # Ignore permission errors
                        
                        # Execute the custom launcher directly
                        cmd = f'cd "{project_path}" && echo "🚀 Using custom launcher: {custom_launcher_path}" && bash "{custom_launcher_path.absolute()}"'
                        print(f"🚀 [UNIFIED] Custom launcher command: {cmd}")
                        
                        terminal_result = self.open_terminal(cmd)
                        
                        if "Terminal launched successfully!" in terminal_result:
                            print(f"🚀 [UNIFIED] SUCCESS: Custom launcher executed")
                            logger.launch_success(project_name)
                            return f"✅ Launched {project_name} (Custom Launcher) - Terminal opened"
                        else:
                            print(f"🚀 [UNIFIED] ERROR: Failed to execute custom launcher")
                            logger.launch_error(project_name, f"Custom launcher failed: {terminal_result}")
                            return f"❌ Failed to start {project_name} with custom launcher: {terminal_result}"
                    
                    print(f"🚀 [UNIFIED] ❌ No custom launcher found, generating one...")
                    print(f"🚀 [UNIFIED] Creating custom launcher for {project_name}...")
                    
                    # Generate a custom launcher using AI analysis
                    try:
                        from qwen_launch_analyzer import QwenLaunchAnalyzer
                        analyzer = QwenLaunchAnalyzer()
                        
                        # Create custom launcher template with AI-generated command
                        custom_launcher_path_str = analyzer.create_custom_launcher_template(
                            project_path, project_name, ""  # Let it auto-detect the best command
                        )
                        
                        if custom_launcher_path_str and Path(custom_launcher_path_str).exists():
                            print(f"🚀 [UNIFIED] ✅ Generated custom launcher: {custom_launcher_path_str}")
                            
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
                            print(f"🚀 [UNIFIED] Generated launcher command: {cmd}")
                            
                            terminal_result = self.open_terminal(cmd)
                            
                            if "Terminal launched successfully!" in terminal_result:
                                print(f"🚀 [UNIFIED] SUCCESS: Generated custom launcher executed")
                                logger.launch_success(project_name)
                                return f"✅ Launched {project_name} (Generated Custom Launcher) - Terminal opened"
                            else:
                                print(f"🚀 [UNIFIED] ERROR: Failed to execute generated custom launcher")
                                logger.launch_error(project_name, f"Generated custom launcher failed: {terminal_result}")
                                return f"❌ Failed to start {project_name} with generated custom launcher: {terminal_result}"
                        else:
                            print(f"🚀 [UNIFIED] ❌ Failed to generate custom launcher")
                            return f"❌ Failed to generate custom launcher for {project_name}"
                            
                    except Exception as e:
                        print(f"🚀 [UNIFIED] ❌ Error generating custom launcher: {str(e)}")
                        return f"❌ Error generating custom launcher for {project_name}: {str(e)}"
                        
                except Exception as e:
                    error_msg = str(e)
                    print(f"🚀 [UNIFIED] EXCEPTION: {error_msg}")
                    logger.launch_error(project_name, error_msg)
                    return f"❌ Error launching project: {error_msg}"
            
            # Note: Search events are wired up in the main function scope
            
            manual_scan_btn.click(
                handle_manual_scan,
                outputs=[status_display, projects_display]
            )
            
            def handle_process_dirty():
                try:
                    cleanup_count = 0
                    if self.scanner:
                        # Get actual cleanup count first
                        cleanup_count = self.scanner._cleanup_inactive_projects()
                        # Then trigger dirty project processing
                        self.scanner.trigger_dirty_cleanup()
                    
                    self.load_projects_from_db()
                    stats = db.get_stats()
                    
                    status_parts = [f"**Projects:** {stats['active_projects']}"]
                    if stats['dirty_projects'] > 0:
                        status_parts.append(f"**Pending Updates:** {stats['dirty_projects']}")
                    
                    # Show actual cleanup results
                    if cleanup_count > 0:
                        status_parts.append(f"**Cleaned:** {cleanup_count} launcher files")
                    else:
                        status_parts.append("**System:** Clean")
                    
                    status_md = f"**Status:** Processing Complete • {' • '.join(status_parts)}"
                    projects_html = self.create_projects_grid(self.current_projects, api_port)
                    return status_md, projects_html
                except Exception as e:
                    return f"**Status:** Processing Error: {str(e)}", gr.update()
            
            process_dirty_btn.click(
                handle_process_dirty,
                outputs=[status_display, projects_display]
            )
            
            refresh_btn.click(
                handle_refresh,
                outputs=[status_display, projects_display]
            )
            
            # Wire up hidden refresh trigger for automatic refresh from JavaScript
            hidden_refresh_trigger.click(
                handle_refresh,
                outputs=[status_display, projects_display]
            )
            
            # Wire up sort dropdown handlers
            sort_by_dropdown.change(
                handle_sort_change,
                inputs=[sort_by_dropdown, sort_direction_dropdown],
                outputs=[projects_display]
            )
            
            sort_direction_dropdown.change(
                handle_sort_change,
                inputs=[sort_by_dropdown, sort_direction_dropdown],
                outputs=[projects_display]
            )
            
            # Wire up launch trigger for Gradio-native launch handling
            launch_trigger.click(
                handle_launch,
                inputs=[project_name_input, project_path_input],
                outputs=[status_display]  # Show launch result in status
            )
            
            # Add JavaScript for launch functionality and favorite/hide buttons
            gr.HTML(f"""
            <script>
            // Launch functionality is handled by global functions
            console.log('🚀 [JS] App list tab JavaScript loaded');
            </script>
            """)
            
            # Return projects_display so it can be accessed by global search handlers
            return projects_display

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

def find_available_port(start_port=7870, end_port=7890, exclude_ports=None):
    """Find an available port in the specified range, excluding certain ports"""
    
    if exclude_ports is None:
        exclude_ports = []
    
    print(f"🚀 [UNIFIED] Searching for available port in range {start_port}-{end_port}, excluding {exclude_ports}")
    
    for port in range(start_port, end_port + 1):
        if port in exclude_ports:
            print(f"🚀 [UNIFIED] Port {port} excluded, skipping...")
            continue
            
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                print(f"🚀 [UNIFIED] Found available port: {port}")
                return port
        except OSError:
            print(f"🚀 [UNIFIED] Port {port} is in use, trying next...")
    
    print(f"🚀 [UNIFIED] No available ports found in range {start_port}-{end_port}")
    return None

def main():
    """Main application entry point with argument parsing"""
    parser = argparse.ArgumentParser(description="Unified AI Project Launcher")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Enable verbose logging (show INFO level logs)")
    parser.add_argument("--port", "-p", type=int, default=7870,
                       help="Port for Gradio interface (default: 7870)")
    parser.add_argument("--api-port", type=int, default=7871,
                       help="Port for launch API server (default: 7871)")
    parser.add_argument("--no-api", action="store_true",
                       help="Disable the launch API server")
    
    args = parser.parse_args()
    
    # Load configuration with fallback handling
    try:
        if not config_exists():
            print("⚠️  Config file not found, creating default configuration")
            if create_default_config():
                print("✅ Default config.json created")
            else:
                print("❌ Failed to create default config.json")
        config = load_config()
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        sys.exit(1)
    
    # Create main launcher
    launcher = UnifiedLauncher(config, verbose=args.verbose)
    
    if args.verbose:
        print("🚀 [VERBOSE] Starting Unified AI Launcher")
        print(f"🚀 [VERBOSE] Gradio port: {args.port}")
        print(f"🚀 [VERBOSE] API port: {args.api_port}")
        print(f"🚀 [VERBOSE] API enabled: {not args.no_api}")
    
    # Start API server if enabled
    api_server_thread = None
    if not args.no_api:
        try:
            if args.verbose:
                print(f"🚀 [VERBOSE] Starting Launch API Server on port {args.api_port}...")
            api_server_thread = start_api_server(port=args.api_port, launcher=launcher)
            if args.verbose:
                print(f"🚀 [VERBOSE] Launch API Server started successfully")
        except Exception as e:
            print(f"❌ Failed to start API server: {e}")
            if not args.verbose:
                print("Use --verbose for more details")
    
    # Determine if we should default to settings tab (config missing or empty)
    default_tab = "settings" if not config.get('index_directories') else "app_list"
    
    # Create the main interface with custom tab buttons for URL routing
    with gr.Blocks(title="🚀 AI Project Launcher", theme=gr.themes.Soft()) as app:
        # Add CSS for modern dark mode design
        gr.HTML("""
        <style>
        /* Global Dark Mode Color Scheme */
        :root {
            /* Core Background Colors */
            --bg-primary: #0f1419;        /* Main background - deep dark blue */
            --bg-secondary: #1a1f2e;      /* Card/surface background */
            --bg-tertiary: #252a3a;       /* Elevated surfaces */
            --bg-hover: #2d3448;          /* Hover states */
            
            /* Accent Colors */
            --accent-blue: #64b5f6;       /* Primary blue accent */
            --accent-purple: #9c27b0;     /* Secondary purple */
            --accent-green: #4caf50;      /* Success/positive */
            --accent-orange: #ff9800;     /* Warning/attention */
            --accent-red: #f44336;        /* Error/negative */
            
            /* Text Colors */
            --text-primary: #e8eaed;      /* Primary text - light gray */
            --text-secondary: #9aa0a6;    /* Secondary text - muted */
            --text-muted: #5f6368;        /* Subtle text */
            --text-accent: #64b5f6;       /* Accent text */
            
            /* Border and Divider Colors */
            --border-primary: #3c4043;    /* Main borders */
            --border-secondary: #5f6368;  /* Stronger borders */
            --border-accent: #64b5f6;     /* Accent borders */
            
            /* Shadow and Effects */
            --shadow-light: 0 2px 8px rgba(0,0,0,0.3);
            --shadow-medium: 0 4px 16px rgba(0,0,0,0.4);
            --shadow-heavy: 0 8px 24px rgba(0,0,0,0.5);
            
            /* Gradients */
            --gradient-primary: linear-gradient(135deg, var(--bg-secondary), var(--bg-tertiary));
            --gradient-accent: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
        }
        
        /* Global Overrides for Dark Mode */
        * {
            scrollbar-width: thin;
            scrollbar-color: var(--border-secondary) var(--bg-secondary);
        }
        
        *::-webkit-scrollbar {
            width: 8px;
        }
        
        *::-webkit-scrollbar-track {
            background: var(--bg-secondary);
        }
        
        *::-webkit-scrollbar-thumb {
            background: var(--border-secondary);
            border-radius: 4px;
        }
        
        *::-webkit-scrollbar-thumb:hover {
            background: var(--text-muted);
        }
        
        /* Fixed navigation bar - dark and professional */
        .nav-container {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            right: 0 !important;
            width: 100% !important;
            z-index: 9999 !important;
            background: var(--bg-secondary) !important;
            border-bottom: 1px solid var(--border-primary) !important;
            box-shadow: var(--shadow-medium) !important;
            padding: 8px 16px !important;
            backdrop-filter: blur(20px) !important;
        }
        
        /* Navigation buttons - dark mode styling */
        .nav-container .gradio-button {
            margin: 0 6px !important;
            font-weight: 500 !important;
            font-size: 14px !important;
            padding: 8px 20px !important;
            border-radius: 8px !important;
            transition: all 0.2s ease !important;
            box-shadow: none !important;
            border: 1px solid var(--border-primary) !important;
            background: var(--bg-tertiary) !important;
            color: var(--text-secondary) !important;
        }
        
        .nav-container .gradio-button:hover {
            transform: translateY(-1px) !important;
            box-shadow: var(--shadow-light) !important;
            background: var(--bg-hover) !important;
            color: var(--text-primary) !important;
        }
        
        /* Primary (active) button */
        .nav-container .gradio-button.primary {
            background: var(--accent-blue) !important;
            border: 1px solid var(--accent-blue) !important;
            color: var(--bg-primary) !important;
            font-weight: 600 !important;
        }
        
        .nav-container .gradio-button.primary:hover {
            background: #81c4f7 !important;
            border-color: #81c4f7 !important;
        }
        
        /* Secondary (inactive) button */
        .nav-container .gradio-button.secondary {
            background: var(--bg-tertiary) !important;
            border: 1px solid var(--border-primary) !important;
            color: var(--text-secondary) !important;
        }
        
        /* Fixed search container - dark mode */
        .fixed-search-container {
            position: fixed !important;
            top: 50px !important;
            left: 0 !important;
            right: 0 !important;
            width: 100% !important;
            z-index: 9998 !important;
            background: var(--bg-secondary) !important;
            border-bottom: 1px solid var(--border-primary) !important;
            padding: 8px 20px !important;
            box-shadow: var(--shadow-light) !important;
        }
        
        /* Main content area - dark background */
        .main-content {
            margin-top: 110px !important;
            padding-top: 0 !important;
            background: var(--bg-primary) !important;
            min-height: calc(100vh - 110px) !important;
        }
        
        /* When search is not visible, reduce main content margin */
        .main-content.no-search {
            margin-top: 60px !important;
            min-height: calc(100vh - 60px) !important;
        }
        
        /* Global body and gradio overrides */
        body, .gradio-container {
            background: var(--bg-primary) !important;
            color: var(--text-primary) !important;
        }
        
        /* App header - dark mode */
        .app-header {
            text-align: center !important;
            padding: 16px 20px 12px 20px !important;
            margin: 0 !important;
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }
        
        .app-header h1 {
            color: var(--text-primary) !important;
            margin: 0 0 4px 0 !important;
            font-weight: 600 !important;
            font-size: 24px !important;
        }
        
        .app-header p {
            color: var(--text-secondary) !important;
            margin: 0 !important;
            font-size: 14px !important;
            font-weight: 400 !important;
        }
        
        /* Warning message - dark mode */
        .config-warning {
            background: var(--bg-secondary) !important;
            border: 1px solid var(--accent-orange) !important;
            border-radius: 8px !important;
            padding: 12px 16px !important;
            margin: 0 20px 16px 20px !important;
            color: var(--accent-orange) !important;
            font-weight: 500 !important;
            font-size: 14px !important;
        }
        
        /* Status and controls - dark mode */
        .status-controls {
            background: var(--bg-secondary) !important;
            border: 1px solid var(--border-primary) !important;
            border-radius: 8px !important;
            padding: 12px 16px !important;
            margin: 0 20px 16px 20px !important;
            box-shadow: var(--shadow-light) !important;
        }
        
        .status-controls .gradio-button {
            background: var(--bg-tertiary) !important;
            border: 1px solid var(--border-primary) !important;
            color: var(--text-secondary) !important;
            border-radius: 6px !important;
            padding: 6px 12px !important;
            font-size: 13px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease !important;
        }
        
        .status-controls .gradio-button:hover {
            background: var(--accent-blue) !important;
            color: var(--bg-primary) !important;
            border-color: var(--accent-blue) !important;
        }
        
        /* Projects section header */
        .projects-section h3 {
            color: var(--text-primary) !important;
            font-weight: 600 !important;
            font-size: 18px !important;
            margin: 0 0 12px 0 !important;
        }
        
        /* Hidden launch controls - present in DOM but invisible to users */
        .hidden-launch-controls {
            position: absolute !important;
            top: -9999px !important;
            left: -9999px !important;
            width: 1px !important;
            height: 1px !important;
            overflow: hidden !important;
            opacity: 0 !important;
            visibility: hidden !important;
            z-index: -1 !important;
        }
        
        /* Keep child elements accessible to JavaScript but invisible */
        .hidden-launch-controls input,
        .hidden-launch-controls textarea,
        .hidden-launch-controls button {
            visibility: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }
        
        /* Hidden toggle controls for favorite/hidden functionality */
        .hidden-toggle-controls {
            position: absolute !important;
            top: -9999px !important;
            left: -9999px !important;
            width: 1px !important;
            height: 1px !important;
            overflow: hidden !important;
            opacity: 0 !important;
            visibility: hidden !important;
            z-index: -1 !important;
        }
        
        /* Keep toggle elements accessible to JavaScript but invisible */
        .hidden-toggle-controls input,
        .hidden-toggle-controls textarea,
        .hidden-toggle-controls button {
            visibility: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }

        /* Mobile responsiveness */
        @media (max-width: 768px) {
            .nav-container {
                padding: 6px 12px !important;
            }
            
            .nav-container .gradio-button {
                margin: 0 3px !important;
                font-size: 12px !important;
                padding: 6px 14px !important;
            }
            
            .fixed-search-container {
                top: 44px !important;
                padding: 6px 16px !important;
            }
            
            .main-content {
                margin-top: 94px !important;
                min-height: calc(100vh - 94px) !important;
            }
            
            .main-content.no-search {
                margin-top: 50px !important;
                min-height: calc(100vh - 50px) !important;
            }
            
            .app-header h1 {
                font-size: 20px !important;
            }
            
            .app-header p {
                font-size: 13px !important;
            }
        }
        </style>
        """)
        
        # State management for URL routing
        current_main_tab = gr.State(value=default_tab)
        current_subtab = gr.State(value="query")
        
        # Main tab buttons - Fixed navigation bar
        with gr.Row(elem_classes="nav-container"):
            app_list_btn = gr.Button("📱 App List", variant="primary" if default_tab == "app_list" else "secondary", size="lg")
            database_btn = gr.Button("🗄️ Database", variant="secondary", size="lg")
            settings_btn = gr.Button("⚙️ Settings", variant="primary" if default_tab == "settings" else "secondary", size="lg")
        
        # Fixed search bar for app list (only visible when app list is active)
        with gr.Row(elem_classes="fixed-search-container", visible=(default_tab == "app_list")) as fixed_search_row:
            with gr.Column(scale=1, min_width=120):
                gr.HTML('<div class="search-label">🔍 Search</div>')
            with gr.Column(scale=8):
                fixed_search_input = gr.Textbox(
                    placeholder="Type to search projects by name, description, path, or environment...",
                    elem_classes="search-input",
                    show_label=False,
                    container=False
                )
            with gr.Column(scale=1, min_width=50):
                fixed_clear_search_btn = gr.Button("✖️", size="sm", elem_classes="search-clear-btn")
        
        # Main content area with top margin to account for fixed header and search
        with gr.Column(elem_classes="main-content"):
            # App header
            with gr.Column(elem_classes="app-header"):
                gr.HTML("<h1>🚀 AI Project Launcher</h1>")
                gr.HTML("<p>Unified interface for discovering, managing, and launching your AI projects</p>")
            
            # Show configuration warning if needed
            if not config.get('index_directories'):
                with gr.Column(elem_classes="config-warning"):
                    gr.HTML("⚠️ <strong>Configuration Required:</strong> No directories configured for indexing. Please configure directories in the Settings tab.")
            
            # Content areas
            with gr.Column(visible=(default_tab == "app_list")) as app_list_content:
                if config.get('index_directories'):
                    projects_display = launcher.build_app_list_tab(args.api_port)
                else:
                    gr.Markdown("### 📁 No Directories Configured")
                    gr.Markdown("Please configure directories to index in the **Settings** tab before using the launcher.")
                    projects_display = None
            
            with gr.Column(visible=False) as database_content:
                build_database_ui(launcher=launcher)
            
            # Settings tab content
            with gr.Column(visible=(default_tab == "settings")) as settings_content:
                build_settings_ui()
        
        # Hidden Gradio components for favorite/hidden toggles - present in DOM but visually hidden
        with gr.Row(elem_classes="hidden-toggle-controls"):  # CSS hidden components for JavaScript access
            toggle_favorite_path = gr.Textbox(label="Favorite Path", elem_id="toggle_favorite_path", show_label=False, container=False)
            toggle_hidden_path = gr.Textbox(label="Hidden Path", elem_id="toggle_hidden_path", show_label=False, container=False)
            favorite_trigger = gr.Button("Toggle Favorite", elem_id="favorite_trigger", size="sm")
            hidden_trigger = gr.Button("Toggle Hidden", elem_id="hidden_trigger", size="sm")
        
        # Handler functions for Gradio-native favorite/hidden toggles
        def handle_toggle_favorite(project_path):
            """Handle toggling favorite status via Gradio - direct database access"""
            try:
                if not project_path or project_path.strip() == "":
                    return "❌ No project path provided"
                
                # Use database directly to avoid ad blocker issues
                new_status = db.toggle_favorite_status(project_path)
                status_text = "added to favorites" if new_status else "removed from favorites"
                
                print(f"✅ [GRADIO] Project {status_text}: {project_path}")
                
                # Reload projects to update UI state
                launcher.load_projects_from_db()
                
                return f"✅ Project {status_text}"
                    
            except Exception as e:
                error_msg = f"Error toggling favorite: {str(e)}"
                print(f"❌ [GRADIO] {error_msg}")
                return f"❌ {error_msg}"
        
        def handle_toggle_hidden(project_path):
            """Handle toggling hidden status via Gradio - direct database access"""
            try:
                if not project_path or project_path.strip() == "":
                    return "❌ No project path provided"
                
                # Use database directly to avoid ad blocker issues  
                new_status = db.toggle_hidden_status(project_path)
                status_text = "hidden" if new_status else "visible"
                
                print(f"✅ [GRADIO] Project set to {status_text}: {project_path}")
                
                # Reload projects to update UI state
                launcher.load_projects_from_db()
                
                return f"✅ Project set to {status_text}"
                    
            except Exception as e:
                error_msg = f"Error toggling hidden status: {str(e)}"
                print(f"❌ [GRADIO] {error_msg}")
                return f"❌ {error_msg}"
        
        # Tab switching functions
        def switch_to_app_list():
            return (
                "app_list",  # current_main_tab
                "",  # current_subtab  
                gr.update(variant="primary"),  # app_list_btn
                gr.update(variant="secondary"),  # database_btn
                gr.update(variant="secondary"),  # settings_btn
                gr.update(visible=True),  # app_list_content
                gr.update(visible=False),  # database_content
                gr.update(visible=False),  # settings_content
                gr.update(visible=True),  # fixed_search_row - show search bar
            )
        
        def switch_to_database():
            return (
                "database",  # current_main_tab
                "query",  # current_subtab
                gr.update(variant="secondary"),  # app_list_btn
                gr.update(variant="primary"),  # database_btn
                gr.update(variant="secondary"),  # settings_btn
                gr.update(visible=False),  # app_list_content
                gr.update(visible=True),  # database_content
                gr.update(visible=False),  # settings_content
                gr.update(visible=False),  # fixed_search_row - hide search bar
            )
        
        def switch_to_settings():
            return (
                "settings",  # current_main_tab
                "",  # current_subtab
                gr.update(variant="secondary"),  # app_list_btn
                gr.update(variant="secondary"),  # database_btn
                gr.update(variant="primary"),  # settings_btn
                gr.update(visible=False),  # app_list_content
                gr.update(visible=False),  # database_content
                gr.update(visible=True),  # settings_content
                gr.update(visible=False),  # fixed_search_row - hide search bar
            )
        
        # Wire up main tab buttons
        app_list_btn.click(
            fn=switch_to_app_list,
            outputs=[
                current_main_tab, current_subtab,
                app_list_btn, database_btn, settings_btn,
                app_list_content, database_content, settings_content,
                fixed_search_row
            ]
        )
        
        database_btn.click(
            fn=switch_to_database,
            outputs=[
                current_main_tab, current_subtab,
                app_list_btn, database_btn, settings_btn,
                app_list_content, database_content, settings_content,
                fixed_search_row
            ]
        )
        
        settings_btn.click(
            fn=switch_to_settings,
            outputs=[
                current_main_tab, current_subtab,
                app_list_btn, database_btn, settings_btn,
                app_list_content, database_content, settings_content,
                fixed_search_row
            ]
        )
        
        # Wire up Gradio components for favorite/hidden toggles  
        favorite_trigger.click(
            handle_toggle_favorite,
            inputs=[toggle_favorite_path],
            outputs=[]  # No direct UI updates - JavaScript will handle refresh
        )
        
        hidden_trigger.click(
            handle_toggle_hidden,
            inputs=[toggle_hidden_path],
            outputs=[]  # No direct UI updates - JavaScript will handle refresh
        )
        
        # Wire up fixed search bar events
        def handle_fixed_search(query):
            """Handle search from the fixed search bar"""
            if hasattr(launcher, 'filter_projects'):
                filtered_projects = launcher.filter_projects(query)
                return launcher.create_projects_grid(filtered_projects, args.api_port)
            return launcher.create_projects_grid(launcher.current_projects, args.api_port)
        
        def clear_fixed_search():
            """Clear the fixed search bar"""
            return "", launcher.create_projects_grid(launcher.current_projects, args.api_port)
        
        fixed_search_input.change(
            handle_fixed_search,
            inputs=[fixed_search_input],
            outputs=[projects_display] if projects_display else []
        )
        
        fixed_clear_search_btn.click(
            clear_fixed_search,
            outputs=[fixed_search_input, projects_display] if projects_display else [fixed_search_input]
        )
        
        # JavaScript for URL management
        app.load(
            fn=None,
            inputs=[],
            outputs=[],
            js=f"""
            function() {{
                console.log('🚀 Launcher URL Router: Initializing...');
                
                // Make API port available globally first
                window.api_port = {args.api_port};
                
                // Define global callAPI function to ensure it's always available
                window.callAPI = function(endpoint, method = 'GET', body = null, successCallback = null) {{
                    console.log(`🌐 [GLOBAL] API call to: ${{endpoint}}`);
                    
                    const options = {{
                        method: method,
                        headers: method === 'POST' ? {{ 'Content-Type': 'application/json' }} : {{}}
                    }};
                    
                    if (body && method === 'POST') {{
                        options.body = JSON.stringify(body);
                    }}
                    
                    const url = `http://localhost:${{window.api_port}}${{endpoint}}`;
                    console.log(`🌐 [GLOBAL] Full URL: ${{url}}`);
                    console.log(`🌐 [GLOBAL] Options:`, options);
                    
                    return fetch(url, options)
                        .then(response => {{
                            console.log(`🌐 [GLOBAL] Response status: ${{response.status}}`);
                            if (!response.ok) {{
                                throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
                            }}
                            return response.json();
                        }})
                        .then(data => {{
                            console.log(`🌐 [GLOBAL] API response for ${{endpoint}}:`, data);
                            if (data.success) {{
                                if (successCallback) successCallback(data);
                                // Always refresh projects after successful API calls
                                if (window.refreshProjects) {{
                                    window.refreshProjects();
                                }}
                                return data;
                            }} else {{
                                console.error(`🌐 [GLOBAL] API call failed for ${{endpoint}}:`, data.error);
                                throw new Error(data.error || 'API call failed');
                            }}
                        }})
                        .catch(error => {{
                            console.error(`🌐 [GLOBAL] Error calling ${{endpoint}}:`, error);
                            
                            // Additional debugging for blocked requests
                            if (error.message && error.message.includes('Failed to fetch')) {{
                                console.error('🚫 [GLOBAL] Request was blocked - possible causes:');
                                console.error('  1. Ad blocker or browser extension');
                                console.error('  2. CORS policy (though CORS is configured)');
                                console.error('  3. Network connectivity issue');
                                console.error('  4. API server not running');
                                console.error(`  5. Check if API server is accessible at: http://localhost:${{window.api_port}}/health`);
                            }}
                            
                            throw error;
                        }});
                }};
                
                // Global refresh function - accessible from anywhere
                window.refreshProjects = function() {{
                    console.log('🔄 [GLOBAL] Refreshing projects...');
                    
                    // Try multiple methods to find and trigger refresh
                    let refreshTriggered = false;
                    
                    // Method 1: Try hidden refresh trigger
                    const hiddenRefreshBtn = document.querySelector('#hidden_refresh_trigger');
                    if (hiddenRefreshBtn) {{
                        hiddenRefreshBtn.click();
                        console.log('🔄 [GLOBAL] Used hidden refresh trigger');
                        refreshTriggered = true;
                    }}
                    
                    // Method 2: Try main refresh button
                    if (!refreshTriggered) {{
                        const mainRefreshBtn = document.querySelector('button[aria-label*="Refresh"]') || 
                                              Array.from(document.querySelectorAll('button')).find(btn => 
                                                  btn.textContent.includes('♻️') || btn.textContent.includes('Refresh'));
                        if (mainRefreshBtn) {{
                            mainRefreshBtn.click();
                            console.log('🔄 [GLOBAL] Used main refresh button');
                            refreshTriggered = true;
                        }}
                    }}
                    
                    if (!refreshTriggered) {{
                        console.warn('🔄 [GLOBAL] No refresh method found');
                    }}
                    
                    return refreshTriggered;
                }};
                
                // Health check function to test API connectivity
                window.testAPIConnection = function() {{
                    console.log('🔍 [HEALTH] Testing API connection...');
                    window.callAPI('/health', 'GET')
                        .then(data => {{
                            console.log('✅ [HEALTH] API server is reachable:', data);
                            return true;
                        }})
                        .catch(error => {{
                            console.error('❌ [HEALTH] API server is not reachable:', error);
                            return false;
                        }});
                }};
                

                
                window.toggleHiddenSection = function() {{
                    const section = document.getElementById('hidden-projects-section');
                    const arrow = document.getElementById('hidden-toggle-arrow');
                    
                    if (section && arrow) {{
                        if (section.style.display === 'none') {{
                            section.style.display = 'block';
                            arrow.textContent = '▲';
                        }} else {{
                            section.style.display = 'none';
                            arrow.textContent = '▼';
                        }}
                    }}
                }};
                
                        // Define global setupLaunchButtons function
        window.setupLaunchButtons = function() {{
            // Find all launch buttons and attach Gradio-native event handlers
            const launchButtons = document.querySelectorAll('[id^="launch_btn_"]:not(.gradio-configured)');
            if (launchButtons.length === 0) {{
                return; // No new buttons to configure
            }}
            
            console.log('🚀 [JS] Setting up', launchButtons.length, 'NEW launch buttons with Gradio handlers');
            
            launchButtons.forEach(button => {{
                // Mark as configured to prevent re-processing
                button.classList.add('gradio-configured');
                
                button.addEventListener('click', function() {{
                            const projectName = this.getAttribute('data-project-name');
                            const projectPath = this.getAttribute('data-project-path');
                            const projectIndex = this.getAttribute('data-project-index');
                            
                                                console.log('🚀 [JS] Launch request via Gradio:', projectIndex, projectName, 'at', projectPath);
                    
                    // Use Gradio's native component system - no external API calls
                    const nameInput = document.querySelector('#project_name_data input, #project_name_data textarea');
                    const pathInput = document.querySelector('#project_path_data input, #project_path_data textarea');
                    const launchBtn = document.querySelector('#launch_trigger');
                    
                    console.log('🔍 [JS] Component search results:', {{
                        nameInput: nameInput ? 'FOUND' : 'MISSING',
                        pathInput: pathInput ? 'FOUND' : 'MISSING', 
                        launchBtn: launchBtn ? 'FOUND' : 'MISSING',
                        nameInputDetails: nameInput ? nameInput.tagName + '#' + nameInput.id : 'null',
                        pathInputDetails: pathInput ? pathInput.tagName + '#' + pathInput.id : 'null',
                        launchBtnDetails: launchBtn ? launchBtn.tagName + '#' + launchBtn.id : 'null'
                    }});
                            
                            if (nameInput && pathInput && launchBtn) {{
                                // Set values in hidden Gradio components
                                nameInput.value = projectName;
                                nameInput.dispatchEvent(new Event('input', {{bubbles: true}}));
                                nameInput.dispatchEvent(new Event('change', {{bubbles: true}}));
                                
                                pathInput.value = projectPath;
                                pathInput.dispatchEvent(new Event('input', {{bubbles: true}}));
                                pathInput.dispatchEvent(new Event('change', {{bubbles: true}}));
                                
                                                        // Trigger Gradio launch button
                        setTimeout(() => {{
                            launchBtn.click();
                            console.log('✅ [JS] Launch triggered via Gradio components');
                        }}, 100);
                    }} else {{
                        console.error('❌ [JS] Could not find Gradio launch components');
                        console.log('Available elements:', {{
                            nameInput: nameInput ? 'found' : 'missing',
                            pathInput: pathInput ? 'found' : 'missing',
                            launchBtn: launchBtn ? 'found' : 'missing'
                        }});
                    }}
                }});
            }});
            
            console.log('✅ [JS] Configured', launchButtons.length, 'launch buttons for Gradio communication');
        }};
                
                // Override global toggleFavorite and toggleHidden with Gradio-native versions
                window.toggleFavorite = function(projectPath) {{
                    console.log('🌟 [JS] Toggle favorite via Gradio for:', projectPath);
                    
                    // Use hidden Gradio components to avoid ad blocker interference
                    const pathInput = document.querySelector('#toggle_favorite_path input, #toggle_favorite_path textarea');
                    const favoriteBtn = document.querySelector('#favorite_trigger');
                    
                    if (pathInput && favoriteBtn) {{
                        // Set the project path in hidden input
                        pathInput.value = projectPath;
                        pathInput.dispatchEvent(new Event('input', {{bubbles: true}}));
                        pathInput.dispatchEvent(new Event('change', {{bubbles: true}}));
                        
                        // Trigger the hidden button
                        setTimeout(() => {{
                            favoriteBtn.click();
                            console.log('✅ [JS] Favorite toggle triggered via Gradio components');
                            
                            // Refresh projects after a short delay
                            setTimeout(() => {{
                                if (window.refreshProjects) {{
                                    window.refreshProjects();
                                }}
                            }}, 500);
                        }}, 100);
                    }} else {{
                        console.error('❌ [JS] Could not find Gradio favorite components');
                        console.log('Available elements:', {{
                            pathInput: pathInput ? 'found' : 'missing',
                            favoriteBtn: favoriteBtn ? 'found' : 'missing'
                        }});
                    }}
                }};
                
                window.toggleHidden = function(projectPath) {{
                    console.log('👻 [JS] Toggle hidden via Gradio for:', projectPath);
                    
                    // Use hidden Gradio components to avoid ad blocker interference
                    const pathInput = document.querySelector('#toggle_hidden_path input, #toggle_hidden_path textarea');
                    const hiddenBtn = document.querySelector('#hidden_trigger');
                    
                    if (pathInput && hiddenBtn) {{
                        // Set the project path in hidden input
                        pathInput.value = projectPath;
                        pathInput.dispatchEvent(new Event('input', {{bubbles: true}}));
                        pathInput.dispatchEvent(new Event('change', {{bubbles: true}}));
                        
                        // Trigger the hidden button
                        setTimeout(() => {{
                            hiddenBtn.click();
                            console.log('✅ [JS] Hidden toggle triggered via Gradio components');
                            
                            // Refresh projects after a short delay
                            setTimeout(() => {{
                                if (window.refreshProjects) {{
                                    window.refreshProjects();
                                }}
                            }}, 500);
                        }}, 100);
                    }} else {{
                        console.error('❌ [JS] Could not find Gradio hidden components');
                        console.log('Available elements:', {{
                            pathInput: pathInput ? 'found' : 'missing',
                            hiddenBtn: hiddenBtn ? 'found' : 'missing'
                        }});
                    }}
                }};
                
                // Set up launch buttons when page loads
                setTimeout(() => {{
                    window.setupLaunchButtons();
                    console.log('🚀 [JS] Launch buttons configured for Gradio-native handling');
                }}, 1000);
                
                        // Re-setup when projects grid updates (debounced to prevent infinite loops)
        let setupTimeout = null;
        const observer = new MutationObserver((mutations) => {{
            let hasNewLaunchButtons = false;
            
            mutations.forEach((mutation) => {{
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {{
                    mutation.addedNodes.forEach((node) => {{
                        if (node.nodeType === 1) {{
                            // Check if this node or its children contain NEW launch buttons (not already configured)
                            const newButtons = (node.id && node.id.startsWith('launch_btn_') && !node.classList.contains('gradio-configured')) ||
                                             (node.querySelector && node.querySelector('[id^="launch_btn_"]:not(.gradio-configured)'));
                            if (newButtons) {{
                                hasNewLaunchButtons = true;
                            }}
                        }}
                    }});
                }}
            }});
            
            if (hasNewLaunchButtons) {{
                // Debounce to prevent rapid firing
                clearTimeout(setupTimeout);
                setupTimeout = setTimeout(() => {{
                    console.log('🔄 [JS] New launch buttons detected, configuring...');
                    window.setupLaunchButtons();
                }}, 200);
            }}
        }});
        observer.observe(document.body, {{ childList: true, subtree: true }});
                
                console.log('🌟 [JS] Global functions loaded via app.load():', {{
                    toggleFavorite: typeof window.toggleFavorite,
                    toggleHidden: typeof window.toggleHidden,
                    toggleHiddenSection: typeof window.toggleHiddenSection,
                    setupLaunchButtons: typeof window.setupLaunchButtons,
                    api_port: window.api_port
                }});
                
                // Debug: Log all elements with IDs to see what's available
                console.log('🔍 [DEBUG] All elements with IDs in the document:');
                const allElementsWithIds = document.querySelectorAll('*[id]');
                allElementsWithIds.forEach(el => {{
                    console.log('  -', el.tagName, el.id, el.type || 'no-type', el.style.display || 'default-display');
                }});
                
                console.log('🔍 [DEBUG] Total elements with IDs:', allElementsWithIds.length);
                
                // Debug: Specifically look for any hidden elements
                console.log('🔍 [DEBUG] Hidden elements (display: none):');
                document.querySelectorAll('*[style*="display: none"], *[style*="display:none"]').forEach(el => {{
                    console.log('  -', el.tagName, el.id || 'no-id', el.className || 'no-class');
                }});
                
                // Debug: Look for Gradio containers
                console.log('🔍 [DEBUG] Gradio containers:');
                document.querySelectorAll('[class*="gradio"], [id*="gradio"]').forEach(el => {{
                    console.log('  -', el.tagName, el.id || 'no-id', el.className || 'no-class');
                }});
                
                // Function to update URL
                function updateURL(tab, subtab = '') {{
                    const url = new URL(window.location);
                    url.searchParams.set('tab', tab);
                    
                    if (subtab && subtab !== '') {{
                        url.searchParams.set('subtab', subtab);
                    }} else {{
                        url.searchParams.delete('subtab');
                    }}
                    
                    window.history.pushState({{tab: tab, subtab: subtab}}, '', url);
                    console.log('🔗 URL updated:', url.href);
                }}
                
                // Function to activate tab from URL on page load
                function activateTabFromURL() {{
                    const urlParams = new URLSearchParams(window.location.search);
                    const requestedTab = urlParams.get('tab') || '{default_tab}';
                    const requestedSubtab = urlParams.get('subtab') || 'query';
                    
                    console.log(`📍 Activating from URL: tab=${{requestedTab}}, subtab=${{requestedSubtab}}`);
                    
                    // Find and click the appropriate main tab button
                    setTimeout(() => {{
                        const buttons = document.querySelectorAll('button');
                        
                        for (const button of buttons) {{
                            const buttonText = button.textContent.toLowerCase().trim();
                            
                            if ((requestedTab === 'app_list' && buttonText === 'app list') ||
                                (requestedTab === 'database' && buttonText === 'database') ||
                                (requestedTab === 'settings' && buttonText === 'settings')) {{
                                console.log(`🎯 Clicking main tab: ${{button.textContent}}`);
                                button.click();
                                
                                // If database tab, also click subtab
                                if (requestedTab === 'database') {{
                                    setTimeout(() => {{
                                        activateSubtab(requestedSubtab);
                                    }}, 300);
                                }}
                                break;
                            }}
                        }}
                    }}, 500);
                }}
                
                // Function to activate subtab
                function activateSubtab(requestedSubtab) {{
                    console.log(`🎯 Looking for subtab: ${{requestedSubtab}}`);
                    
                    const buttons = document.querySelectorAll('button');
                    
                    for (const button of buttons) {{
                        const buttonText = button.textContent.toLowerCase().replace(/[🔍📋📊🛠️]/g, '').trim();
                        
                        if ((requestedSubtab === 'query' && buttonText === 'query') ||
                            (requestedSubtab === 'schema' && buttonText === 'schema') ||
                            (requestedSubtab === 'statistics' && buttonText === 'statistics') ||
                            (requestedSubtab === 'tools' && buttonText === 'tools')) {{
                            console.log(`🎯 Clicking subtab: ${{button.textContent}}`);
                            button.click();
                            break;
                        }}
                    }}
                }}
                
                // Monitor button clicks to update URL
                function setupButtonMonitoring() {{
                    const observer = new MutationObserver((mutations) => {{
                        mutations.forEach((mutation) => {{
                            if (mutation.type === 'attributes' && mutation.attributeName === 'class') {{
                                const button = mutation.target;
                                
                                if (button.tagName === 'BUTTON' && button.classList.contains('primary')) {{
                                    const buttonText = button.textContent.toLowerCase().trim();
                                    console.log(`👆 Button activated: ${{button.textContent}}`);
                                    
                                    // Main tab buttons
                                    if (buttonText === 'app list') {{
                                        updateURL('app_list');
                                    }} else if (buttonText === 'database') {{
                                        updateURL('database', 'query');
                                    }} else if (buttonText === 'settings') {{
                                        updateURL('settings');
                                    }}
                                    // Subtab buttons
                                    else if (buttonText.includes('query')) {{
                                        updateURL('database', 'query');
                                    }} else if (buttonText.includes('schema')) {{
                                        updateURL('database', 'schema');
                                    }} else if (buttonText.includes('statistics')) {{
                                        updateURL('database', 'statistics');
                                    }} else if (buttonText.includes('tools')) {{
                                        updateURL('database', 'tools');
                                    }}
                                }}
                            }}
                        }});
                    }});
                    
                    observer.observe(document.body, {{
                        attributes: true,
                        subtree: true,
                        attributeFilter: ['class']
                    }});
                    
                    console.log('📊 Button monitoring active');
                }}
                
                // Handle browser back/forward
                window.addEventListener('popstate', (event) => {{
                    console.log('⬅️ Browser navigation detected');
                    activateTabFromURL();
                }});
                
                // Initialize
                setTimeout(() => {{
                    setupButtonMonitoring();
                    activateTabFromURL();
                }}, 1000);
                
                return [];
            }}
            """
        )
    
    print("🚀 =================================")
    print("🚀 Unified AI Project Launcher")
    print(f"📱 Web interface: http://localhost:{args.port}")
    if not args.no_api:
        print(f"🌐 Launch API: http://localhost:{args.api_port}")
    print("💾 Using persistent database for project tracking")
    print("🔄 Background scanning enabled")
    print("📊 Database viewer included")
    print("🚀 =================================")
    
    try:
        app.launch(share=False, server_name="0.0.0.0", server_port=args.port)
    except KeyboardInterrupt:
        print("\n🚀 Launcher stopped by user")
        logger.info("Launcher stopped by user")
    except Exception as e:
        print(f"🚀 FATAL ERROR: {str(e)}")
        logger.error(f"Fatal error during startup: {str(e)}")
        if args.verbose:
            import traceback
            print(f"🚀 Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main() 