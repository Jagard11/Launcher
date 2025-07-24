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
from settings_ui import build_settings_ui, config_exists, create_default_config
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
            /* Project cards - will be styled in persistent_launcher.py */
            </style>
            """)
            
            # Note: Search bar is now fixed at the top - removed from here
            
            # Status and controls - compact and clean
            with gr.Row(elem_classes="status-controls"):
                with gr.Column(scale=3):
                    status_display = gr.Markdown(f"""
📊 **{stats['active_projects']} Projects** • 🔄 **{stats['dirty_projects']} Pending Updates**
                    """)
                
                with gr.Column(scale=2):
                    with gr.Row():
                        manual_scan_btn = gr.Button("🔄 Scan", size="sm")
                        process_dirty_btn = gr.Button("🤖 Process", size="sm")
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
                
            # Hidden refresh button for JavaScript to trigger automatic refresh
            with gr.Row(visible=False):
                hidden_refresh_trigger = gr.Button("Hidden Refresh", elem_id="hidden_refresh_trigger")
            
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
            
            # Note: Search events are wired up in the main function scope
            
            manual_scan_btn.click(
                handle_manual_scan,
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
            
            launch_trigger.click(
                handle_launch,
                inputs=[project_name_input, project_path_input],
                outputs=[launch_output]
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
                build_database_ui(launcher=launcher.persistent_launcher)
            
            # Settings tab content
            with gr.Column(visible=(default_tab == "settings")) as settings_content:
                build_settings_ui()
        
        # Global hidden components for favorite/hidden toggles (always available)
        with gr.Row(visible=True):  # Temporarily visible for debugging
            gr.HTML("<h4>🔧 DEBUG: Hidden Toggle Components (should be hidden in production)</h4>")
            toggle_favorite_path = gr.Textbox(label="DEBUG: Favorite Path", elem_id="toggle_favorite_path")
            toggle_hidden_path = gr.Textbox(label="DEBUG: Hidden Path", elem_id="toggle_hidden_path")
            favorite_trigger = gr.Button("DEBUG: Toggle Favorite", elem_id="favorite_trigger")
            hidden_trigger = gr.Button("DEBUG: Toggle Hidden", elem_id="hidden_trigger")
        
        # Global handler functions for favorite/hidden toggles
        def handle_toggle_favorite(project_path):
            """Handle toggling favorite status via Gradio"""
            try:
                import requests
                response = requests.post(
                    f"http://localhost:{args.api_port}/api/toggle-favorite",
                    headers={"Content-Type": "application/json"},
                    json={"project_path": project_path}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        print(f"✅ [GRADIO] Favorite toggled successfully for: {project_path}")
                        return f"✅ Favorite toggled for project"
                    else:
                        print(f"❌ [GRADIO] Failed to toggle favorite: {data.get('error')}")
                        return f"❌ Failed to toggle favorite: {data.get('error')}"
                else:
                    print(f"❌ [GRADIO] API request failed: {response.status_code}")
                    return f"❌ API request failed: {response.status_code}"
                    
            except Exception as e:
                print(f"❌ [GRADIO] Error toggling favorite: {str(e)}")
                return f"❌ Error toggling favorite: {str(e)}"
        
        def handle_toggle_hidden(project_path):
            """Handle toggling hidden status via Gradio"""
            try:
                import requests
                response = requests.post(
                    f"http://localhost:{args.api_port}/api/toggle-hidden",
                    headers={"Content-Type": "application/json"},
                    json={"project_path": project_path}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        print(f"✅ [GRADIO] Hidden status toggled successfully for: {project_path}")
                        return f"✅ Hidden status toggled for project"
                    else:
                        print(f"❌ [GRADIO] Failed to toggle hidden: {data.get('error')}")
                        return f"❌ Failed to toggle hidden: {data.get('error')}"
                else:
                    print(f"❌ [GRADIO] API request failed: {response.status_code}")
                    return f"❌ API request failed: {response.status_code}"
                    
            except Exception as e:
                print(f"❌ [GRADIO] Error toggling hidden: {str(e)}")
                return f"❌ Error toggling hidden: {str(e)}"
        
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
        
        # Wire up global favorite and hidden toggles (after content areas are defined)
        # Note: These components are global so they work across all tabs
        favorite_trigger.click(
            handle_toggle_favorite,
            inputs=[toggle_favorite_path],
            outputs=[]  # We'll handle UI updates within the function
        )
        
        hidden_trigger.click(
            handle_toggle_hidden,
            inputs=[toggle_hidden_path],
            outputs=[]  # We'll handle UI updates within the function
        )
        
        # Wire up fixed search bar events
        def handle_fixed_search(query):
            """Handle search from the fixed search bar"""
            if hasattr(launcher, 'persistent_launcher') and hasattr(launcher.persistent_launcher, 'filter_projects'):
                filtered_projects = launcher.persistent_launcher.filter_projects(query)
                return launcher.persistent_launcher.create_projects_grid(filtered_projects, args.api_port)
            return launcher.persistent_launcher.create_projects_grid(launcher.persistent_launcher.current_projects, args.api_port)
        
        def clear_fixed_search():
            """Clear the fixed search bar"""
            return "", launcher.persistent_launcher.create_projects_grid(launcher.persistent_launcher.current_projects, args.api_port)
        
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
                console.log('🚀 Unified Launcher URL Router: Initializing...');
                
                // Make API port available globally first
                window.api_port = {args.api_port};
                
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
                
                // Define global functions for favorite/hide functionality
                window.toggleFavorite = function(projectPath) {{
                    console.log('🌟 [JS] Toggle favorite for:', projectPath);
                    
                    // Helper function to find elements with retry
                    function findElements(attempt = 1, maxAttempts = 5) {{
                        console.log(`🌟 [JS] Attempt ${{attempt}}/${{maxAttempts}} to find elements`);
                        
                        // Try multiple selector strategies for Gradio textboxes
                        let pathInput = document.querySelector('#toggle_favorite_path input') || 
                                       document.querySelector('#toggle_favorite_path textarea') ||
                                       document.querySelector('#toggle_favorite_path [role="textbox"]') ||
                                       document.querySelector('[id*="toggle_favorite_path"] input') ||
                                       document.querySelector('[id*="toggle_favorite_path"] textarea') ||
                                       document.querySelector('#toggle_favorite_path').querySelector('input') ||
                                       document.querySelector('#toggle_favorite_path').querySelector('textarea');
                        
                        let triggerBtn = document.querySelector('#favorite_trigger') ||
                                        document.querySelector('[id*="favorite_trigger"]') ||
                                        document.querySelector('button[id*="favorite_trigger"]');
                        
                        console.log('🌟 [JS] Element search results:', {{
                            pathInput: pathInput ? 'found' : 'not found',
                            triggerBtn: triggerBtn ? 'found' : 'not found',
                            pathInputId: pathInput ? pathInput.id : 'none',
                            triggerBtnId: triggerBtn ? triggerBtn.id : 'none'
                        }});
                        
                        if (pathInput && triggerBtn) {{
                            console.log('🌟 [JS] Elements found! Proceeding with toggle...');
                            
                            pathInput.value = projectPath;
                            pathInput.dispatchEvent(new Event('input'));
                            pathInput.dispatchEvent(new Event('change'));
                            
                            // Trigger the toggle button
                            setTimeout(() => {{
                                console.log('🌟 [JS] Clicking trigger button...');
                                triggerBtn.click();
                                
                                // Wait a moment for the API call to complete, then refresh
                                setTimeout(() => {{
                                    console.log('🌟 [JS] Calling global refresh...');
                                    if (window.refreshProjects) {{
                                        window.refreshProjects();
                                    }} else {{
                                        console.warn('🌟 [JS] Global refresh function not available');
                                    }}
                                }}, 500);
                            }}, 100);
                            
                            return true;
                        }} else if (attempt < maxAttempts) {{
                            // Log all available elements for debugging
                            console.log('🌟 [JS] Available elements with "toggle" or "favorite" in ID:');
                            document.querySelectorAll('[id*="toggle"], [id*="favorite"]').forEach(el => {{
                                console.log('  -', el.tagName, el.id, el.className);
                            }});
                            
                            // Retry after a delay
                            setTimeout(() => findElements(attempt + 1, maxAttempts), 500);
                            return false;
                        }} else {{
                            console.error('🌟 [JS] Could not find favorite toggle elements after', maxAttempts, 'attempts');
                            console.log('🌟 [JS] All elements in document:');
                            document.querySelectorAll('*[id]').forEach(el => {{
                                if (el.id.includes('toggle') || el.id.includes('favorite')) {{
                                    console.log('  -', el.tagName, el.id, el.type || 'no-type');
                                }}
                            }});
                            return false;
                        }}
                    }}
                    
                    findElements();
                }};
                
                window.toggleHidden = function(projectPath) {{
                    console.log('👻 [JS] Toggle hidden for:', projectPath);
                    
                    // Helper function to find elements with retry
                    function findElements(attempt = 1, maxAttempts = 5) {{
                        console.log(`👻 [JS] Attempt ${{attempt}}/${{maxAttempts}} to find elements`);
                        
                        // Try multiple selector strategies for Gradio textboxes
                        let pathInput = document.querySelector('#toggle_hidden_path input') || 
                                       document.querySelector('#toggle_hidden_path textarea') ||
                                       document.querySelector('#toggle_hidden_path [role="textbox"]') ||
                                       document.querySelector('[id*="toggle_hidden_path"] input') ||
                                       document.querySelector('[id*="toggle_hidden_path"] textarea') ||
                                       document.querySelector('#toggle_hidden_path').querySelector('input') ||
                                       document.querySelector('#toggle_hidden_path').querySelector('textarea');
                        
                        let triggerBtn = document.querySelector('#hidden_trigger') ||
                                        document.querySelector('[id*="hidden_trigger"]') ||
                                        document.querySelector('button[id*="hidden_trigger"]');
                        
                        console.log('👻 [JS] Element search results:', {{
                            pathInput: pathInput ? 'found' : 'not found',
                            triggerBtn: triggerBtn ? 'found' : 'not found',
                            pathInputId: pathInput ? pathInput.id : 'none',
                            triggerBtnId: triggerBtn ? triggerBtn.id : 'none'
                        }});
                        
                        if (pathInput && triggerBtn) {{
                            console.log('👻 [JS] Elements found! Proceeding with toggle...');
                            
                            pathInput.value = projectPath;
                            pathInput.dispatchEvent(new Event('input'));
                            pathInput.dispatchEvent(new Event('change'));
                            
                            // Trigger the toggle button
                            setTimeout(() => {{
                                console.log('👻 [JS] Clicking trigger button...');
                                triggerBtn.click();
                                
                                // Wait a moment for the API call to complete, then refresh
                                setTimeout(() => {{
                                    console.log('👻 [JS] Calling global refresh...');
                                    if (window.refreshProjects) {{
                                        window.refreshProjects();
                                    }} else {{
                                        console.warn('👻 [JS] Global refresh function not available');
                                    }}
                                }}, 500);
                            }}, 100);
                            
                            return true;
                        }} else if (attempt < maxAttempts) {{
                            // Log all available elements for debugging
                            console.log('👻 [JS] Available elements with "toggle" or "hidden" in ID:');
                            document.querySelectorAll('[id*="toggle"], [id*="hidden"]').forEach(el => {{
                                console.log('  -', el.tagName, el.id, el.className);
                            }});
                            
                            // Retry after a delay
                            setTimeout(() => findElements(attempt + 1, maxAttempts), 500);
                            return false;
                        }} else {{
                            console.error('👻 [JS] Could not find hidden toggle elements after', maxAttempts, 'attempts');
                            console.log('👻 [JS] All elements in document:');
                            document.querySelectorAll('*[id]').forEach(el => {{
                                if (el.id.includes('toggle') || el.id.includes('hidden')) {{
                                    console.log('  -', el.tagName, el.id, el.type || 'no-type');
                                }}
                            }});
                            return false;
                        }}
                    }}
                    
                    findElements();
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
                
                window.launchProject = function(projectName, projectPath) {{
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
                }};
                
                console.log('🌟 [JS] Global functions loaded via app.load():', {{
                    toggleFavorite: typeof window.toggleFavorite,
                    toggleHidden: typeof window.toggleHidden,
                    toggleHiddenSection: typeof window.toggleHiddenSection,
                    launchProject: typeof window.launchProject,
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