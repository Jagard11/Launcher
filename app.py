import gradio as gr
import json
from pathlib import Path
from launcher_ui import build_launcher_ui
from database_ui import build_database_ui

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

def main():
    """Main application entry point"""
    config = load_config()
    
    # Create the main interface with tabs
    with gr.Blocks(title="AI Launcher", theme=gr.themes.Soft()) as app:
        gr.Markdown("# AI Project Launcher")
        gr.Markdown("Discover and launch your AI projects with automatic environment detection")
        
        with gr.Tabs() as tabs:
            # App List tab (default)
            with gr.Tab("App List", id="app_list") as app_list_tab:
                build_launcher_ui(config)
            
            # Database tab
            with gr.Tab("Database", id="database") as database_tab:
                build_database_ui()
    
    return app

if __name__ == "__main__":
    app = main()
    app.launch(share=False, server_name="0.0.0.0", server_port=7860) 