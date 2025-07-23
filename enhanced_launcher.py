#!/usr/bin/env python3

import gradio as gr
import json
from pathlib import Path
from project_scanner import ProjectScanner
from environment_detector import EnvironmentDetector
from icon_generator import generate_project_icon
from ollama_summarizer import OllamaSummarizer
from logger import logger
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor
import threading

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

def launch_project(project_path: str, project_name: str):
    """Launch a project with its detected environment"""
    try:
        env_detector = EnvironmentDetector()
        env_info = env_detector.detect_environment(project_path)
        
        logger.launch_attempt(project_name, project_path, env_info['type'])
        
        if env_info['type'] == 'none':
            error_msg = f"No Python environment detected for {project_name}"
            logger.launch_error(project_name, error_msg)
            return f"❌ {error_msg}"
        
        # Find main script with more options
        main_scripts = ['app.py', 'main.py', 'run.py', 'start.py', 'launch.py', 'server.py', 'webui.py']
        script_path = None
        
        logger.info(f"Looking for main script in {project_path}")
        for script in main_scripts:
            potential_path = Path(project_path) / script
            logger.debug(f"Checking for {potential_path}")
            if potential_path.exists():
                script_path = potential_path
                logger.info(f"Found main script: {script_path}")
                break
        
        if not script_path:
            # Try to find any Python file that might be the main one
            py_files = list(Path(project_path).glob('*.py'))
            logger.info(f"No standard main script found. Found {len(py_files)} Python files")
            
            if py_files:
                # Use the first Python file as fallback
                script_path = py_files[0]
                logger.warning(f"Using fallback script: {script_path}")
            else:
                error_msg = f"No Python script found in {project_name}"
                logger.launch_error(project_name, error_msg)
                return f"❌ {error_msg}"
        
        # Prepare launch command with better error handling
        script_name = script_path.name
        project_path_escaped = project_path.replace('"', '\\"')
        
        if env_info['type'] == 'conda':
            env_name = env_info.get('name', 'base')
            cmd = f'gnome-terminal --title="{project_name}" -- bash -c "echo \\"Launching {project_name}...\\" && cd \\"{project_path_escaped}\\" && echo \\"Activating conda environment: {env_name}\\" && conda activate {env_name} && echo \\"Running: python3 {script_name}\\" && python3 {script_name}; echo \\"Press Enter to close...\\"; read"'
        elif env_info['type'] == 'venv':
            activate_path = env_info.get('activate_path', '')
            cmd = f'gnome-terminal --title="{project_name}" -- bash -c "echo \\"Launching {project_name}...\\" && cd \\"{project_path_escaped}\\" && echo \\"Activating virtual environment\\" && source \\"{activate_path}\\" && echo \\"Running: python3 {script_name}\\" && python3 {script_name}; echo \\"Press Enter to close...\\"; read"'
        elif env_info['type'] == 'poetry':
            cmd = f'gnome-terminal --title="{project_name}" -- bash -c "echo \\"Launching {project_name}...\\" && cd \\"{project_path_escaped}\\" && echo \\"Using Poetry environment\\" && poetry run python3 {script_name}; echo \\"Press Enter to close...\\"; read"'
        elif env_info['type'] == 'pipenv':
            cmd = f'gnome-terminal --title="{project_name}" -- bash -c "echo \\"Launching {project_name}...\\" && cd \\"{project_path_escaped}\\" && echo \\"Using Pipenv environment\\" && pipenv run python3 {script_name}; echo \\"Press Enter to close...\\"; read"'
        else:
            cmd = f'gnome-terminal --title="{project_name}" -- bash -c "echo \\"Launching {project_name}...\\" && cd \\"{project_path_escaped}\\" && echo \\"Using system Python\\" && python3 {script_name}; echo \\"Press Enter to close...\\"; read"'
        
        logger.info(f"Executing launch command for {project_name}")
        logger.debug(f"Command: {cmd}")
        
        # Execute the command
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Give it a moment to start
        import time
        time.sleep(1)
        
        # Check if the process started successfully
        if process.poll() is None or process.poll() == 0:
            logger.launch_success(project_name)
            return f"✅ Launched {project_name} in new terminal (Environment: {env_info['type']})"
        else:
            stdout, stderr = process.communicate()
            error_msg = f"Failed to start terminal: {stderr.decode() if stderr else 'Unknown error'}"
            logger.launch_error(project_name, error_msg)
            return f"❌ {error_msg}"
        
    except Exception as e:
        error_msg = str(e)
        logger.launch_error(project_name, error_msg)
        return f"❌ Error launching project: {error_msg}"

def generate_project_summary(project, summarizer):
    """Generate summary for a single project using Ollama"""
    try:
        # Generate documentation summary
        doc_summary = summarizer.summarize_documentation(project['path'])
        
        # Generate code summary  
        code_summary = summarizer.summarize_code(project['path'])
        
        # Generate final tooltip and description
        tooltip, description = summarizer.generate_final_summary(
            project['name'], doc_summary, code_summary
        )
        
        return {
            'tooltip': tooltip,
            'description': description
        }
    except Exception as e:
        print(f"Error generating summary for {project['name']}: {e}")
        return {
            'tooltip': f"AI project: {project['name']}",
            'description': f"AI/ML project located at {project['path']}"
        }

def main():
    config = load_config()
    scanner = ProjectScanner(config['index_directories'])
    env_detector = EnvironmentDetector()
    summarizer = OllamaSummarizer()
    
    # Global storage
    current_projects = []
    
    def scan_projects_basic():
        """Scan for projects without Ollama summaries"""
        projects = scanner.scan_directories()
        
        project_data = []
        for project in projects:
            icon = generate_project_icon(project['name'])
            env_info = env_detector.detect_environment(project['path'])
            
            project_data.append({
                'name': project['name'],
                'path': project['path'],
                'icon': icon,
                'env_type': env_info['type'],
                'env_name': env_info.get('name', 'N/A'),
                'tooltip': f"AI project: {project['name']}",
                'description': f"Located at: {project['path']}"
            })
        
        return project_data
    
    def enhance_with_ollama(projects):
        """Add Ollama-generated summaries to projects"""
        def process_project(project):
            summary = generate_project_summary(project, summarizer)
            project.update(summary)
            return project
        
        # Process projects in parallel for better performance
        with ThreadPoolExecutor(max_workers=3) as executor:
            enhanced_projects = list(executor.map(process_project, projects))
        
        return enhanced_projects
    
    def create_project_card(project, index):
        """Create HTML for a single project card"""
        return f"""
        <div class="project-card" style="
            border: 1px solid #ddd; 
            border-radius: 12px; 
            padding: 20px; 
            text-align: center; 
            background: linear-gradient(145deg, #f9f9f9, #ffffff);
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.2s;
            cursor: pointer;
            margin: 10px;
        " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
            <img src="{project['icon']}" style="width: 80px; height: 80px; margin: 10px; border-radius: 8px;" />
            <h3 style="margin: 15px 0 10px 0; font-size: 16px; color: #333; font-weight: bold;">{project['name']}</h3>
            <p style="font-size: 12px; color: #666; margin: 5px 0; background: #e9f5ff; padding: 4px 8px; border-radius: 12px; display: inline-block;">
                {project['env_type']} environment
            </p>
            <p style="font-size: 13px; color: #555; margin: 10px 0; line-height: 1.4; height: 60px; overflow: hidden;">
                {project['tooltip'][:120]}...
            </p>
            <button onclick="launchProject({index})" style="
                background: linear-gradient(145deg, #007bff, #0056b3); 
                color: white; 
                border: none; 
                padding: 12px 24px; 
                border-radius: 8px; 
                cursor: pointer; 
                margin-top: 10px;
                font-weight: bold;
                transition: all 0.2s;
            " onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                🚀 Launch
            </button>
        </div>
        """
    
    def create_project_grid(projects):
        """Create a responsive grid of project cards"""
        grid_html = f"""
        <div style="
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); 
            gap: 20px; 
            padding: 20px;
            background: #f5f5f5;
            border-radius: 12px;
        ">
        """
        
        for i, project in enumerate(projects):
            grid_html += create_project_card(project, i)
        
        grid_html += "</div>"
        
        # Add JavaScript for launching
        grid_html += """
        <script>
        function launchProject(index) {
            // This would trigger the Gradio backend function
            console.log('Launching project at index:', index);
        }
        </script>
        """
        
        return grid_html
    
    def scan_and_display():
        nonlocal current_projects
        logger.info("Starting project scan...")
        current_projects = scan_projects_basic()
        grid_html = create_project_grid(current_projects)
        logger.info(f"Scan completed: {len(current_projects)} projects found")
        return grid_html, f"✅ Found {len(current_projects)} projects (basic scan)"
    
    def enhance_with_ai():
        nonlocal current_projects
        if not current_projects:
            return "❌ Please scan for projects first", "No projects to enhance"
        
        try:
            logger.info(f"Starting AI enhancement for {len(current_projects)} projects...")
            enhanced_projects = enhance_with_ollama(current_projects)
            current_projects = enhanced_projects
            grid_html = create_project_grid(current_projects)
            logger.info("AI enhancement completed successfully")
            return grid_html, f"✅ Enhanced {len(current_projects)} projects with AI descriptions"
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error during AI enhancement: {error_msg}")
            return f"❌ Error enhancing projects: {error_msg}", "Enhancement failed"
    
    def launch_by_name(project_name):
        """Launch project by name"""
        for project in current_projects:
            if project['name'] == project_name:
                result = launch_project(project['path'], project['name'])
                return result
        return "❌ Project not found"
    
    def get_project_details(project_name):
        """Get detailed information about a project"""
        for project in current_projects:
            if project['name'] == project_name:
                env_info = env_detector.detect_environment(project['path'])
                return f"""
## {project['name']}

**Path:** `{project['path']}`

**Environment:** {env_info['type']} ({env_info.get('name', 'N/A')})

**Description:** {project.get('description', 'No description available')}

**Size:** {project.get('size', 'Unknown')}
                """
        return "Project not found"
    
    # Create the Gradio interface
    with gr.Blocks(title="🚀 AI Project Launcher", theme=gr.themes.Soft()) as interface:
        gr.Markdown("# 🚀 AI Project Launcher")
        gr.Markdown("Discover and launch your AI projects with automatic environment detection and AI-powered descriptions")
        
        with gr.Row():
            scan_btn = gr.Button("🔍 Quick Scan", variant="primary", size="lg")
            enhance_btn = gr.Button("🤖 Enhance with AI", variant="secondary", size="lg")
            status = gr.Textbox(label="Status", interactive=False, scale=2)
        
        projects_display = gr.HTML(label="Projects")
        
        with gr.Row():
            with gr.Column(scale=2):
                project_selector = gr.Dropdown(
                    label="Select Project", 
                    choices=[], 
                    interactive=True
                )
                launch_btn = gr.Button("🚀 Launch Selected", variant="primary")
                
            with gr.Column(scale=1):
                launch_output = gr.Textbox(label="Launch Output", interactive=False)
        
        project_details = gr.Markdown("Select a project to see details")
        
        # Event handlers
        scan_btn.click(
            scan_and_display,
            outputs=[projects_display, status]
        ).then(
            lambda: gr.Dropdown(choices=[project['name'] for project in current_projects]),
            outputs=[project_selector]
        )
        
        enhance_btn.click(
            enhance_with_ai,
            outputs=[projects_display, status]
        )
        
        project_selector.change(
            get_project_details,
            inputs=[project_selector],
            outputs=[project_details]
        )
        
        launch_btn.click(
            launch_by_name,
            inputs=[project_selector],
            outputs=[launch_output]
        )
    
    return interface

if __name__ == "__main__":
    app = main()
    print("🚀 Starting Enhanced AI Project Launcher...")
    print("📱 Access the web interface at: http://localhost:7861")
    print("💡 Features:")
    print("   - Automatic project discovery")
    print("   - Environment detection (conda, venv, poetry, etc.)")
    print("   - AI-powered project descriptions")
    print("   - One-click launching")
    app.launch(share=False, server_name="0.0.0.0", server_port=7861) 