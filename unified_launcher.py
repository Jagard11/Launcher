#!/usr/bin/env python3

import gradio as gr
import argparse
import sys
import logging
from pathlib import Path
from typing import Dict

# Import existing modules
from project_database import db
from database_ui import build_database_ui
from background_scanner import get_scanner
from environment_detector import EnvironmentDetector
from logger import logger
from launch_api_server import start_api_server
from persistent_launcher import PersistentLauncher, load_config, find_available_port

class UnifiedLauncher:
    def __init__(self, config: dict, verbose: bool = False):
        self.config = config
        self.verbose = verbose
        self.persistent_launcher = PersistentLauncher(config)
        
        # Configure logging based on verbose flag
        if verbose:
            # Set the underlying logger to INFO level for verbose output
            logging.getLogger("AILauncher").setLevel(logging.INFO)
            logging.getLogger().setLevel(logging.INFO)
        else:
            # Set to WARNING level for minimal output
            logging.getLogger("AILauncher").setLevel(logging.WARNING)
            logging.getLogger().setLevel(logging.WARNING)
    
    def build_app_list_tab(self, api_port: int):
        """Build the app list tab with existing functionality"""
        # Initialize the persistent launcher
        self.persistent_launcher.initialize()
        
        # Get initial stats
        stats = db.get_stats()
        
        with gr.Column():
            # Add custom CSS for styling (simplified version)
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
            }
            .project-card * {
                color: #2c3e50 !important;
            }
            </style>
            """)
            
            # Search bar
            with gr.Row(elem_classes="search-container"):
                with gr.Column():
                    gr.HTML('<div style="margin-bottom: 10px; font-weight: 600; color: #2c3e50; text-align: center; font-size: 18px;">🔍 Search Projects</div>')
                    with gr.Row():
                        with gr.Column(scale=9):
                            search_input = gr.Textbox(
                                placeholder="Type to search projects by name, description, path, or environment...",
                                elem_classes="search-input",
                                show_label=False,
                                container=False
                            )
                        with gr.Column(scale=1, min_width=60):
                            clear_search_btn = gr.Button("✖️", size="sm")
            
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
            projects_display = gr.HTML(self.persistent_launcher.create_projects_grid(self.persistent_launcher.current_projects, api_port))
            
            # Launch output
            with gr.Row():
                launch_output = gr.Textbox(label="Launch Output", interactive=False)
                project_details = gr.Markdown("Click on a project name to see details")
            
            # Hidden components for instant launches
            with gr.Row(visible=False):
                instant_launch_input = gr.Textbox(elem_id="instant_launch_data")
                project_name_input = gr.Textbox(elem_id="project_name_data")
                project_path_input = gr.Textbox(elem_id="project_path_data")
                launch_trigger = gr.Button("Launch", elem_id="launch_trigger")
            
            # Event handlers (simplified)
            def handle_search(query):
                filtered_projects = []
                if query.strip():
                    query_lower = query.lower()
                    for project in self.persistent_launcher.current_projects:
                        if (query_lower in project.get('name', '').lower() or
                            query_lower in project.get('description', '').lower() or
                            query_lower in project.get('path', '').lower() or
                            query_lower in project.get('environment_type', '').lower()):
                            filtered_projects.append(project)
                else:
                    filtered_projects = self.persistent_launcher.current_projects
                
                return self.persistent_launcher.create_projects_grid(filtered_projects, api_port)
            
            def handle_manual_scan():
                try:
                    scanner = get_scanner()
                    scanner.start_initial_scan()
                    self.persistent_launcher.load_projects()
                    stats = db.get_stats()
                    status_md = f"**Status:** Scan Complete • **Projects:** {stats['active_projects']} • **Pending Updates:** {stats['dirty_projects']}"
                    projects_html = self.persistent_launcher.create_projects_grid(self.persistent_launcher.current_projects, api_port)
                    return status_md, projects_html
                except Exception as e:
                    return f"**Status:** Scan Error: {str(e)}", gr.update()
            
            def handle_refresh():
                self.persistent_launcher.load_projects_from_db()
                stats = db.get_stats()
                status_md = f"**Status:** Refreshed • **Projects:** {stats['active_projects']} • **Pending Updates:** {stats['dirty_projects']}"
                projects_html = self.persistent_launcher.create_projects_grid(self.persistent_launcher.current_projects, api_port)
                return status_md, projects_html
            
            def clear_search():
                projects_html = self.persistent_launcher.create_projects_grid(self.persistent_launcher.current_projects, api_port)
                return "", projects_html
            
            def handle_launch(project_name, project_path):
                try:
                    result = self.persistent_launcher.launch_project_background(project_path, project_name)
                    return result
                except Exception as e:
                    return f"❌ Launch error: {str(e)}"
            
            # Wire up events
            search_input.change(
                handle_search,
                inputs=[search_input],
                outputs=[projects_display]
            )
            
            clear_search_btn.click(
                clear_search,
                outputs=[search_input, projects_display]
            )
            
            manual_scan_btn.click(
                handle_manual_scan,
                outputs=[status_display, projects_display]
            )
            
            refresh_btn.click(
                handle_refresh,
                outputs=[status_display, projects_display]
            )
            
            launch_trigger.click(
                handle_launch,
                inputs=[project_name_input, project_path_input],
                outputs=[launch_output]
            )
            
            # Add JavaScript for launch functionality
            gr.HTML(f"""
            <script>
            function launchProject(projectName, projectPath) {{
                console.log('🚀 [JS] Launch request:', projectName, 'at', projectPath);
                
                // Set hidden inputs
                const nameInput = document.querySelector('#project_name_data input');
                const pathInput = document.querySelector('#project_path_data input');
                const launchBtn = document.querySelector('#launch_trigger');
                
                if (nameInput && pathInput && launchBtn) {{
                    nameInput.value = projectName;
                    nameInput.dispatchEvent(new Event('input'));
                    
                    pathInput.value = projectPath;
                    pathInput.dispatchEvent(new Event('input'));
                    
                    // Trigger launch after a short delay
                    setTimeout(() => {{
                        launchBtn.click();
                    }}, 100);
                }} else {{
                    console.error('🚀 [JS] Could not find required elements');
                }}
            }}
            
            // Make function globally available
            window.launchProject = launchProject;
            </script>
            """)

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
    
    # Load configuration
    try:
        config = load_config()
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        sys.exit(1)
    
    # Create unified launcher
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
            api_server_thread = start_api_server(port=args.api_port, launcher=launcher.persistent_launcher)
            if args.verbose:
                print(f"🚀 [VERBOSE] Launch API Server started successfully")
        except Exception as e:
            print(f"❌ Failed to start API server: {e}")
            if not args.verbose:
                print("Use --verbose for more details")
    
    # Create the main interface with tabs
    with gr.Blocks(title="🚀 AI Project Launcher", theme=gr.themes.Soft()) as app:
        gr.Markdown("# 🚀 AI Project Launcher")
        gr.Markdown("Unified interface for discovering, managing, and launching your AI projects")
        
        with gr.Tabs():
            # App List tab (default)
            with gr.Tab("App List", id="app_list") as app_list_tab:
                launcher.build_app_list_tab(args.api_port)
            
            # Database tab
            with gr.Tab("Database", id="database") as database_tab:
                build_database_ui(launcher=launcher.persistent_launcher)
    
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