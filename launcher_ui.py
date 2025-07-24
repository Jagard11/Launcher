import gradio as gr
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple
from project_scanner import ProjectScanner
from environment_detector import EnvironmentDetector
from ollama_summarizer import OllamaSummarizer
from icon_generator import generate_project_icon
import json

class LauncherUI:
    def __init__(self, config: dict):
        self.config = config
        self.scanner = ProjectScanner(config['index_directories'])
        self.env_detector = EnvironmentDetector()
        self.summarizer = OllamaSummarizer()
        self.projects = []
        
    def scan_projects(self):
        """Scan for projects and generate metadata"""
        self.projects = self.scanner.scan_directories()
        
        # Generate descriptions and tooltips using Ollama
        for project in self.projects:
            try:
                # Generate documentation summary
                doc_summary = self.summarizer.summarize_documentation(project['path'])
                
                # Generate code summary  
                code_summary = self.summarizer.summarize_code(project['path'])
                
                # Generate final tooltip and description
                tooltip, description = self.summarizer.generate_final_summary(
                    project['name'], doc_summary, code_summary
                )
                
                project['tooltip'] = tooltip
                project['description'] = description
                project['icon'] = generate_project_icon(project['name'])
                
            except Exception as e:
                print(f"Error processing {project['name']}: {e}")
                project['tooltip'] = f"AI project: {project['name']}"
                project['description'] = f"Located at: {project['path']}"
                project['icon'] = generate_project_icon(project['name'])
        
        return self.projects
    
    def launch_project(self, project_path: str):
        """Launch a project with its detected environment"""
        try:
            env_info = self.env_detector.detect_environment(project_path)
            
            if env_info['type'] == 'none':
                return f"❌ No Python environment detected for {project_path}"
            
            # Build activation command
            if env_info['type'] == 'conda':
                activate_cmd = f"conda activate {env_info['name']}"
            elif env_info['type'] == 'venv':
                activate_cmd = f"source {env_info['activate_path']}"
            else:
                activate_cmd = ""
            
            # Find main script
            main_scripts = ['app.py', 'main.py', 'run.py', 'start.py']
            script_path = None
            
            for script in main_scripts:
                potential_path = Path(project_path) / script
                if potential_path.exists():
                    script_path = potential_path
                    break
            
            if not script_path:
                return f"❌ No main script found in {project_path}"
            
            # Launch in new terminal
            if env_info['type'] == 'conda':
                cmd = f'gnome-terminal -- bash -c "cd {project_path} && conda activate {env_info["name"]} && python {script_path.name}"'
            elif env_info['type'] == 'venv':
                cmd = f'gnome-terminal -- bash -c "cd {project_path} && source {env_info["activate_path"]} && python {script_path.name}"'
            else:
                cmd = f'gnome-terminal -- bash -c "cd {project_path} && python {script_path.name}"'
            
            subprocess.Popen(cmd, shell=True)
            return f"✅ Launched {Path(project_path).name} in new terminal"
            
        except Exception as e:
            return f"❌ Error launching project: {str(e)}"

def build_launcher_ui(config: dict):
    """Build the launcher UI components"""
    launcher = LauncherUI(config)
    
    with gr.Column():
        with gr.Row():
            scan_btn = gr.Button("🔍 Scan Projects", variant="primary")
            status_text = gr.Textbox(label="Status", interactive=False)
        
        projects_gallery = gr.Gallery(
            label="AI Projects",
            show_label=True,
            elem_id="projects_gallery",
            columns=4,
            rows=2,
            object_fit="contain",
            height="auto"
        )
        
        with gr.Row():
            project_info = gr.Markdown("Select a project to see details")
        
        launch_output = gr.Textbox(label="Launch Output", interactive=False)
        
        def scan_and_display():
            try:
                projects = launcher.scan_projects()
                
                # Prepare gallery items
                gallery_items = []
                for project in projects:
                    gallery_items.append((project['icon'], project['name']))
                
                return gallery_items, f"✅ Scanned {len(projects)} projects"
            except Exception as e:
                return [], f"❌ Error scanning: {str(e)}"
        
        def select_project(evt: gr.SelectData):
            if evt.index < len(launcher.projects):
                project = launcher.projects[evt.index]
                env_info = launcher.env_detector.detect_environment(project['path'])
                
                info_md = f"""
## {project['name']}
**Path:** `{project['path']}`
**Environment:** {env_info['type']} ({env_info.get('name', 'N/A')})
**Description:** {project['description']}
                """
                return info_md
            return "No project selected"
        
        def launch_selected(evt: gr.SelectData):
            if evt.index < len(launcher.projects):
                project = launcher.projects[evt.index]
                result = launcher.launch_project(project['path'])
                return result
            return "No project selected"
        
        # Event handlers
        scan_btn.click(
            scan_and_display,
            outputs=[projects_gallery, status_text]
        )
        
        projects_gallery.select(
            select_project,
            outputs=[project_info]
        )
        
        projects_gallery.select(
            launch_selected,
            outputs=[launch_output]
        ) 