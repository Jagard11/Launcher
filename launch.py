#!/usr/bin/env python3

import gradio as gr
import json
from pathlib import Path
from project_scanner import ProjectScanner
from environment_detector import EnvironmentDetector
from icon_generator import generate_project_icon
import subprocess
import os

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

def launch_project(project_path: str, project_name: str):
    """Launch a project with its detected environment"""
    try:
        env_detector = EnvironmentDetector()
        env_info = env_detector.detect_environment(project_path)
        
        if env_info['type'] == 'none':
            return f"❌ No Python environment detected for {project_name}"
        
        # Find main script
        main_scripts = ['app.py', 'main.py', 'run.py', 'start.py']
        script_path = None
        
        for script in main_scripts:
            potential_path = Path(project_path) / script
            if potential_path.exists():
                script_path = potential_path
                break
        
        if not script_path:
            return f"❌ No main script found in {project_name}"
        
        # Launch in new terminal
        if env_info['type'] == 'conda':
            cmd = f'gnome-terminal -- bash -c "cd {project_path} && conda activate {env_info["name"]} && python3 {script_path.name}"'
        elif env_info['type'] == 'venv':
            cmd = f'gnome-terminal -- bash -c "cd {project_path} && source {env_info["activate_path"]} && python3 {script_path.name}"'
        else:
            cmd = f'gnome-terminal -- bash -c "cd {project_path} && python3 {script_path.name}"'
        
        subprocess.Popen(cmd, shell=True)
        return f"✅ Launched {project_name} in new terminal"
        
    except Exception as e:
        return f"❌ Error launching project: {str(e)}"

def main():
    config = load_config()
    scanner = ProjectScanner(config['index_directories'])
    env_detector = EnvironmentDetector()
    
    def scan_projects():
        """Scan for projects"""
        projects = scanner.scan_directories()
        
        # Generate simple icons and project info
        project_data = []
        for project in projects:
            icon = generate_project_icon(project['name'])
            env_info = env_detector.detect_environment(project['path'])
            
            project_data.append({
                'name': project['name'],
                'path': project['path'],
                'icon': icon,
                'env_type': env_info['type'],
                'env_name': env_info.get('name', 'N/A')
            })
        
        return project_data
    
    def create_project_grid(projects):
        """Create a grid of project buttons"""
        grid_html = "<div style='display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; padding: 20px;'>"
        
        for i, project in enumerate(projects):
            grid_html += f"""
            <div style='border: 1px solid #ddd; border-radius: 8px; padding: 15px; text-align: center; background: #f9f9f9;'>
                <img src='{project['icon']}' style='width: 64px; height: 64px; margin: 10px;' />
                <h4 style='margin: 10px 0; font-size: 14px;'>{project['name']}</h4>
                <p style='font-size: 12px; color: #666; margin: 5px 0;'>Env: {project['env_type']}</p>
                <button onclick='launchProject({i})' style='background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-top: 10px;'>Launch</button>
            </div>
            """
        
        grid_html += "</div>"
        return grid_html
    
    # Global project storage
    current_projects = []
    
    def scan_and_display():
        nonlocal current_projects
        current_projects = scan_projects()
        grid_html = create_project_grid(current_projects)
        return grid_html, f"Found {len(current_projects)} projects"
    
    def launch_selected(project_index):
        if 0 <= project_index < len(current_projects):
            project = current_projects[project_index]
            result = launch_project(project['path'], project['name'])
            return result
        return "Invalid project selection"
    
    # Create Gradio interface
    with gr.Blocks(title="AI Project Launcher", theme=gr.themes.Soft()) as interface:
        gr.Markdown("# 🚀 AI Project Launcher")
        gr.Markdown("Discover and launch your AI projects with automatic environment detection")
        
        with gr.Row():
            scan_btn = gr.Button("🔍 Scan Projects", variant="primary", size="lg")
            status = gr.Textbox(label="Status", interactive=False)
        
        projects_display = gr.HTML()
        launch_output = gr.Textbox(label="Launch Output", interactive=False)
        
        # Event handlers
        scan_btn.click(
            scan_and_display,
            outputs=[projects_display, status]
        )
    
    return interface

if __name__ == "__main__":
    app = main()
    print("Starting AI Project Launcher...")
    print("Access the web interface at: http://localhost:7860")
    app.launch(share=False, server_name="0.0.0.0", server_port=7860) 