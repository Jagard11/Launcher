import gradio as gr
import json
from pathlib import Path
from launcher_ui import build_launcher_ui

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

def main():
    """Main application entry point"""
    config = load_config()
    
    # Create the main interface
    with gr.Blocks(title="AI Launcher", theme=gr.themes.Soft()) as app:
        gr.Markdown("# AI Project Launcher")
        gr.Markdown("Discover and launch your AI projects with automatic environment detection")
        
        # Build the launcher UI
        build_launcher_ui(config)
    
    return app

if __name__ == "__main__":
    app = main()
    app.launch(share=False, server_name="0.0.0.0", server_port=7860) 