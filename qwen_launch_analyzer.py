#!/usr/bin/env python3

import subprocess
import json
import os
import time
import stat
from pathlib import Path
from typing import Optional, Dict, List
from logger import logger
from environment_detector import EnvironmentDetector

class QwenLaunchAnalyzer:
    def __init__(self):
        # Use the available Qwen3 models - prefer smaller ones for speed
        self.primary_model = "qwen3:8b"         # Fast and efficient for most analysis
        self.advanced_model = "qwen3:14b"       # For complex projects
        self.fallback_model = "qwen3:8b"        # Fallback option
        
        # Create custom launchers directory if it doesn't exist
        self.custom_launchers_dir = Path("custom_launchers")
        self.custom_launchers_dir.mkdir(exist_ok=True)
        
    def call_qwen(self, model: str, prompt: str) -> str:
        """Call Qwen model with the specified prompt"""
        start_time = time.time()
        
        # Log the request
        logger.ollama_request(model, prompt[:200] + "..." if len(prompt) > 200 else prompt)
        
        try:
            cmd = ['ollama', 'run', model, prompt]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            
            execution_time = time.time() - start_time
            
            if result.returncode == 0:
                response = result.stdout.strip()
                logger.ollama_response(model, response[:200] + "..." if len(response) > 200 else response, execution_time)
                return response
            else:
                error_msg = f"Return code {result.returncode}: {result.stderr}"
                logger.ollama_error(model, error_msg)
                print(f"❌ Qwen error with {model}: {error_msg}")
                return ""
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            error_msg = f"Call timed out after {execution_time:.1f}s"
            logger.ollama_error(model, error_msg)
            print(f"⏱️ Qwen timeout with {model}: {error_msg}")
            return ""
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            logger.ollama_error(model, error_msg)
            print(f"💥 Qwen exception with {model}: {error_msg}")
            return ""
    
    def check_custom_launcher(self, project_path: str, project_name: str) -> Optional[Dict]:
        """Check if user has created a custom launcher for this project"""
        # Clean project name for filename
        safe_name = "".join(c for c in project_name if c.isalnum() or c in ('-', '_')).strip()
        custom_launcher_path = self.custom_launchers_dir / f"{safe_name}.sh"
        
        if custom_launcher_path.exists():
            return {
                'main_script': f"custom_launchers/{safe_name}.sh",
                'launch_command': f"./custom_launchers/{safe_name}.sh",
                'working_directory': '.',
                'requires_args': '',
                'launch_type': 'custom_launcher',
                'description': f"Custom user-defined launcher for {project_name}",
                'confidence': 1.0,
                'notes': 'User-created custom launcher script',
                'analysis_method': 'custom_override',
                'model_used': 'none',
                'analyzed_at': time.time()
            }
        
        return None
    
    def create_custom_launcher_template(self, project_path: str, project_name: str, suggested_command: str = "") -> str:
        """Create a custom launcher template for the user to edit"""
        safe_name = "".join(c for c in project_name if c.isalnum() or c in ('-', '_')).strip()
        custom_launcher_path = self.custom_launchers_dir / f"{safe_name}.sh"
        
        # If we have a suggested command, use it directly
        if suggested_command and suggested_command.strip():
            launch_command = suggested_command
        else:
            # Determine a good default command based on project analysis
            structure = self.analyze_project_structure(project_path)
            env_detector = EnvironmentDetector()
            env_info = env_detector.detect_environment(project_path)
            
            # Use direct fallback analysis to get a real command
            analysis = self._enhanced_fallback_analysis(
                structure, project_path, project_name, 
                env_info.get('type', 'none'), env_info.get('name', '')
            )
            
            launch_command = analysis.get('launch_command', '')
            
            # If the fallback analysis returns a custom launcher (recursive), use direct heuristics
            if launch_command.startswith('./custom_launchers/'):
                # Use smart detection based on project name and structure
                project_name_lower = project_name.lower()
                
                if "stable" in project_name_lower and "diffusion" in project_name_lower:
                    launch_command = "./webui.sh"
                elif "comfyui" in project_name_lower:
                    launch_command = "python main.py"
                elif "text-generation" in project_name_lower or "oobabooga" in project_name_lower:
                    launch_command = "./start_linux.sh"
                elif "kohya" in project_name_lower:
                    launch_command = "python gui.py"
                elif "invokeai" in project_name_lower:
                    launch_command = "invokeai-web"
                elif "fooocus" in project_name_lower:
                    launch_command = "python launch.py"
                else:
                    # Check for obvious launch files in the project
                    path_obj = Path(project_path)
                    
                    # High priority shell scripts
                    priority_scripts = ['webui.sh', 'start.sh', 'run.sh', 'launch.sh', 'start_linux.sh']
                    for script in priority_scripts:
                        if (path_obj / script).exists():
                            launch_command = f"./{script}"
                            break
                    
                    if launch_command.startswith('./custom_launchers/'):  # Still not found
                        # Framework detection
                        if structure['requirements']:
                            req_text = ' '.join(structure['requirements']).lower()
                            if 'streamlit' in req_text and 'app.py' in structure['python_files']:
                                launch_command = "streamlit run app.py"
                            elif 'gradio' in req_text and 'app.py' in structure['python_files']:
                                launch_command = "python app.py"
                            elif 'fastapi' in req_text and 'main.py' in structure['python_files']:
                                launch_command = "uvicorn main:app --host 0.0.0.0 --port 8000"
                        
                        # Final fallback to common Python files
                        if launch_command.startswith('./custom_launchers/'):
                            common_files = ['app.py', 'main.py', 'run.py', 'server.py']
                            for file in common_files:
                                if file in structure['python_files']:
                                    launch_command = f"python {file}"
                                    break
                            
                            # If still no command found, use the most promising file
                            if launch_command.startswith('./custom_launchers/') and structure['python_files']:
                                launch_command = f"python {structure['python_files'][0]}"
        
        # Final safety check - never create a recursive launcher
        if not launch_command or launch_command.startswith('./custom_launchers/'):
            launch_command = "echo 'Please edit this script to add your launch command'"
        
        template_content = f"""#!/bin/bash
# Custom launcher for {project_name}
# Project path: {project_path}
# 
# Edit this script to customize how this project launches
# The launcher will automatically cd to the project directory before running

set -e  # Exit on error

echo "🚀 Launching {project_name}..."
cd "{project_path}"

# Launch command (auto-generated by AI analysis)
{launch_command}

echo "✅ {project_name} launched"
"""
        
        try:
            with open(custom_launcher_path, 'w') as f:
                f.write(template_content)
            
            # Make it executable
            os.chmod(custom_launcher_path, 0o755)
            
            return str(custom_launcher_path)
        except Exception as e:
            logger.error(f"Failed to create custom launcher template: {e}")
            return ""

    def analyze_project_structure(self, project_path: str) -> Dict:
        """Analyze project structure to understand its layout"""
        path_obj = Path(project_path)
        
        structure = {
            'python_files': [],
            'config_files': [],
            'requirements': [],
            'scripts': [],
            'executable_scripts': [],
            'directories': [],
            'readme_content': '',
            'dockerfile': False,
            'docker_compose': False,
            'package_json': False,
            'makefile': False
        }
        
        try:
            # Get Python files
            for py_file in path_obj.glob('*.py'):
                if py_file.is_file() and py_file.stat().st_size < 100000:  # Max 100KB
                    structure['python_files'].append(py_file.name)
            
            # Get nested Python files (one level deep)
            for subdir in path_obj.iterdir():
                if subdir.is_dir() and not subdir.name.startswith('.'):
                    structure['directories'].append(subdir.name)
                    for py_file in subdir.glob('*.py'):
                        if py_file.is_file() and py_file.stat().st_size < 100000:
                            structure['python_files'].append(f"{subdir.name}/{py_file.name}")
            
            # Get configuration files
            config_patterns = [
                'requirements.txt', 'environment.yml', 'conda.yaml', 'pyproject.toml',
                'Pipfile', 'setup.py', 'config.json', 'config.yaml', 'config.yml',
                '.env', 'settings.py', 'config.py'
            ]
            
            for pattern in config_patterns:
                for config_file in path_obj.glob(pattern):
                    if config_file.is_file():
                        structure['config_files'].append(config_file.name)
                        
                        # Read requirements if small enough
                        if config_file.name == 'requirements.txt' and config_file.stat().st_size < 10000:
                            try:
                                content = config_file.read_text(encoding='utf-8', errors='ignore')
                                structure['requirements'] = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')][:20]
                            except:
                                pass
            
            # Check for special files
            if (path_obj / 'Dockerfile').exists():
                structure['dockerfile'] = True
            if (path_obj / 'docker-compose.yml').exists() or (path_obj / 'docker-compose.yaml').exists():
                structure['docker_compose'] = True
            if (path_obj / 'package.json').exists():
                structure['package_json'] = True
            if (path_obj / 'Makefile').exists() or (path_obj / 'makefile').exists():
                structure['makefile'] = True
            
            # Get README content
            readme_files = list(path_obj.glob('README*')) + list(path_obj.glob('readme*'))
            if readme_files:
                try:
                    readme_content = readme_files[0].read_text(encoding='utf-8', errors='ignore')
                    structure['readme_content'] = readme_content[:3000]  # First 3KB
                except:
                    pass
            
            # Enhanced script detection with executable check
            script_patterns = ['*.sh', '*.bat', 'launch*', 'run*', 'start*', 'webui*']
            for pattern in script_patterns:
                for script_file in path_obj.glob(pattern):
                    if script_file.is_file():
                        structure['scripts'].append(script_file.name)
                        
                        # Check if script is executable
                        try:
                            file_stat = script_file.stat()
                            if file_stat.st_mode & stat.S_IEXEC:
                                structure['executable_scripts'].append(script_file.name)
                        except:
                            pass
        
        except Exception as e:
            logger.error(f"Error analyzing project structure for {project_path}: {e}")
        
        return structure
    
    def generate_launch_command(self, project_path: str, project_name: str, env_type: str = "none", env_name: str = "") -> Dict:
        """Generate intelligent launch command using AI analysis, with user interaction for uncertainty"""
        structure = self.analyze_project_structure(project_path)
        
        # First, check if user has created a custom launcher
        custom_launcher = self.check_custom_launcher(project_path, project_name)
        if custom_launcher:
            return custom_launcher
        
        # Read key files for better context
        key_files_content = self._read_key_files(project_path, structure)
        
        # Create comprehensive context for intelligent AI analysis
        context = f"""
PROJECT ANALYSIS REQUEST

Project: {project_name}
Location: {project_path}
Environment: {env_type} ({env_name})

STRUCTURE ANALYSIS:
- Python files: {structure['python_files'][:15]}
- Script files: {structure['scripts']}
- Executable scripts: {structure['executable_scripts']}
- Configuration files: {structure['config_files']}
- Dependencies: {structure['requirements'][:15]}
- Directories: {structure['directories'][:10]}
- Has Dockerfile: {structure['dockerfile']}
- Has Docker Compose: {structure['docker_compose']}
- Has package.json: {structure['package_json']}
- Has Makefile: {structure['makefile']}

KEY FILES CONTENT:
{key_files_content}

README CONTENT (first 2000 chars):
{structure['readme_content'][:2000]}
"""
        
        # Intelligent AI prompt that encourages analysis and handles uncertainty
        prompt = f"""You are an expert software engineer analyzing a project to determine the best launch method. Analyze this project structure carefully and provide your assessment.

{context}

ANALYSIS INSTRUCTIONS:
1. Read through ALL the information provided carefully
2. Look for clues in README files, script names, dependencies, and project structure
3. Consider what type of application this appears to be (web app, ML training, GUI tool, etc.)
4. Identify ALL possible launch methods you can find
5. Evaluate each method's likelihood of success
6. If you're uncertain or find multiple valid options, indicate this clearly

RESPONSE FORMAT - Return ONLY valid JSON:
{{
    "primary_launch": {{
        "command": "exact command to run",
        "confidence": 0.0-1.0,
        "reasoning": "why you chose this method"
    }},
    "alternative_launches": [
        {{
            "command": "alternative command",
            "confidence": 0.0-1.0,
            "reasoning": "why this might work"
        }}
    ],
    "analysis": {{
        "project_type": "your assessment of what this project is",
        "main_script": "primary entry point file",
        "working_directory": ".",
        "requires_args": "",
        "launch_type": "shell_script|python_script|docker|makefile|framework_specific|custom",
        "description": "brief description of the project",
        "uncertainty_notes": "any concerns or uncertainties",
        "missing_launch_method": false,
        "needs_user_input": false
    }}
}}

IMPORTANT GUIDELINES:
- Shell scripts (.sh) are often preferred for complex setups
- Look for project-specific patterns (webui.sh for web UIs, main.py for Python apps)
- Consider framework requirements (streamlit run for Streamlit, uvicorn for FastAPI)
- Docker projects may prefer docker-compose or docker run
- If no clear launch method exists, set "missing_launch_method": true
- If multiple good options exist or you're unsure, set "needs_user_input": true
- Be honest about uncertainty - don't guess if you're not confident

Return ONLY the JSON response, no other text."""

        # Get AI response
        response = self.call_qwen(self.primary_model, prompt)
        
        if not response:
            # If AI fails, use fallback analysis to create a good custom launcher
            fallback_analysis = self._enhanced_fallback_analysis(structure, project_path, project_name, env_type, env_name)
            fallback_command = fallback_analysis.get('launch_command', 'echo "Please edit this script"')
            
            template_path = self.create_custom_launcher_template(project_path, project_name, fallback_command)
            return {
                'main_script': fallback_analysis.get('main_script', 'unknown'),
                'launch_command': f"./custom_launchers/{Path(template_path).name}",
                'working_directory': '.',
                'requires_args': '',
                'launch_type': 'needs_user_input',
                'description': f"AI analysis failed - using fallback analysis in {template_path}",
                'confidence': fallback_analysis.get('confidence', 0.1),
                'notes': f'AI analysis unavailable. Used fallback heuristics. Custom launcher created at {template_path}.',
                'analysis_method': 'ai_failed_fallback_template',
                'needs_user_input': True,
                'custom_launcher_path': template_path,
                'model_used': 'fallback',
                'analyzed_at': time.time()
            }
        
        try:
            # Parse AI response
            response_clean = self._clean_json_response(response)
            result = json.loads(response_clean)
            
            # Extract primary analysis
            primary = result.get('primary_launch', {})
            analysis = result.get('analysis', {})
            alternatives = result.get('alternative_launches', [])
            
            # Determine if user input is needed - be less aggressive about this
            needs_user_input = (
                analysis.get('needs_user_input', False) or
                analysis.get('missing_launch_method', False) or
                primary.get('confidence', 0) < 0.3  # Only if confidence is very low
                # Removed: len(alternatives) > 1 - having alternatives is good, not a problem!
            )
            
            # ALWAYS create custom launcher files for ALL projects with the best available command
            # Pick the BEST command from primary or alternatives and implement it directly
            best_command = primary.get('command', '')
            
            # If primary command is weak, check alternatives for a better one
            if primary.get('confidence', 0) < 0.5 and alternatives:
                for alt in alternatives:
                    if alt.get('confidence', 0) > primary.get('confidence', 0):
                        best_command = alt.get('command', '')
                        break
            
            # Create launcher with the ACTUAL best command for every project
            custom_launcher_path = None
            if best_command and best_command.strip():
                custom_launcher_path = self.create_custom_launcher_template(
                    project_path, project_name, best_command
                )
            
            # Build final result
            final_result = {
                'main_script': analysis.get('main_script', primary.get('command', '').split()[-1]),
                'launch_command': primary.get('command', 'echo "No launch method determined"'),
                'working_directory': analysis.get('working_directory', '.'),
                'requires_args': analysis.get('requires_args', ''),
                'launch_type': analysis.get('launch_type', 'unknown'),
                'description': analysis.get('description', f"Launch {project_name}"),
                'confidence': primary.get('confidence', 0.0),
                'notes': primary.get('reasoning', '') + (' | ' + analysis.get('uncertainty_notes', '') if analysis.get('uncertainty_notes') else ''),
                'analysis_method': 'qwen_ai_intelligent',
                'model_used': self.primary_model,
                'analyzed_at': time.time(),
                'needs_user_input': needs_user_input,
                'alternatives': alternatives,
                'ai_analysis': analysis
            }
            
            # We always create custom launchers now, but only point to them if confidence is very low
            if custom_launcher_path:
                final_result['custom_launcher_path'] = custom_launcher_path
                # Only use custom launcher path as launch_command if primary confidence is extremely low
                if primary.get('confidence', 0) < 0.3:
                    final_result['launch_command'] = f"./custom_launchers/{Path(custom_launcher_path).name}"
                    final_result['launch_type'] = 'needs_user_input'
                # Otherwise keep the primary command but note that custom launcher exists as backup
            
            return final_result
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse AI analysis for {project_name}: {e}")
            # Fallback to enhanced heuristic analysis
            return self._enhanced_fallback_analysis(structure, project_path, project_name, env_type, env_name)
    
    def update_launch_command_in_db(self, project_path: str, new_launch_data: Dict) -> bool:
        """Update launch command in database with user modifications"""
        try:
            from project_database import db
            
            # Get existing project data
            project_data = db.get_project_by_path(project_path)
            if not project_data:
                logger.error(f"Project not found in database: {project_path}")
                return False
            
            # Update with new launch data
            update_data = {
                'path': project_path,
                'launch_command': new_launch_data.get('launch_command', ''),
                'launch_type': new_launch_data.get('launch_type', 'user_modified'),
                'launch_working_directory': new_launch_data.get('working_directory', '.'),
                'launch_args': new_launch_data.get('requires_args', ''),
                'launch_confidence': new_launch_data.get('confidence', 1.0),
                'launch_notes': f"User modified: {new_launch_data.get('notes', '')}",
                'launch_analysis_method': 'user_override',
                'main_script': new_launch_data.get('main_script', ''),
                'launch_analyzed_at': time.time()
            }
            
            db.upsert_project(update_data)
            logger.info(f"Updated launch command for {project_path}: {new_launch_data.get('launch_command')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update launch command in database: {e}")
            return False
    
    def get_launch_alternatives_for_ui(self, project_path: str, project_name: str) -> Dict:
        """Get launch analysis with alternatives for UI display"""
        analysis = self.generate_launch_command(project_path, project_name)
        
        # Format for UI display
        ui_data = {
            'current_command': analysis.get('launch_command', ''),
            'confidence': analysis.get('confidence', 0.0),
            'needs_user_input': analysis.get('needs_user_input', False),
            'alternatives': analysis.get('alternatives', []),
            'custom_launcher_path': analysis.get('custom_launcher_path'),
            'analysis_notes': analysis.get('notes', ''),
            'project_type': analysis.get('ai_analysis', {}).get('project_type', 'Unknown'),
            'uncertainty_notes': analysis.get('ai_analysis', {}).get('uncertainty_notes', ''),
            'missing_launch_method': analysis.get('ai_analysis', {}).get('missing_launch_method', False)
        }
        
        return ui_data

    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON from Qwen response that may contain thinking tags"""
        if not response:
            return "{}"
        
        # Remove thinking tags if present
        if '<think>' in response:
            # Find the end of thinking section
            think_end = response.find('</think>')
            if think_end != -1:
                response = response[think_end + 8:].strip()
        
        # Look for JSON object starting with {
        start_idx = response.find('{')
        if start_idx == -1:
            return "{}"
        
        # Find matching closing brace
        brace_count = 0
        end_idx = start_idx
        
        for i, char in enumerate(response[start_idx:], start_idx):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i
                    break
        
        if brace_count == 0:
            json_str = response[start_idx:end_idx + 1]
            return json_str
        
        # If we couldn't find complete JSON, return empty object
        return "{}"
    
    def _enhanced_fallback_analysis(self, structure: Dict, project_path: str, project_name: str, env_type: str, env_name: str) -> Dict:
        """Enhanced fallback analysis that prioritizes shell scripts and common patterns"""
        logger.info(f"Using enhanced fallback analysis for {project_name}")
        
        # First check for specific project patterns with lower confidence threshold
        project_type = self.check_custom_launcher(project_path, project_name)
        if project_type:
            return project_type

        # Priority order for launch methods
        launch_type = "unknown"
        main_script = None
        launch_command = None
        confidence = 0.1
        
        # 1. HIGHEST PRIORITY: Executable shell scripts with launch-specific names
        priority_shell_scripts = [
            'webui.sh', 'webui-user.sh', 'start.sh', 'run.sh', 'launch.sh', 
            'start_linux.sh', 'run_linux.sh', 'start_webui.sh'
        ]
        
        for script in priority_shell_scripts:
            if script in structure['executable_scripts']:
                main_script = script
                launch_command = f"./{script}"
                launch_type = "shell_script"
                confidence = 0.9
                break
            elif script in structure['scripts']:
                # Check if file exists and try to make it executable
                script_path = Path(project_path) / script
                if script_path.exists():
                    main_script = script
                    launch_command = f"./{script}"
                    launch_type = "shell_script"
                    confidence = 0.85
                    break
        
        # 2. Framework-specific detection based on requirements
        if not main_script and structure['requirements']:
            req_text = ' '.join(structure['requirements']).lower()
            
            # Streamlit detection
            if 'streamlit' in req_text and any(script in structure['python_files'] for script in ['app.py', 'main.py']):
                for script in ['app.py', 'main.py']:
                    if script in structure['python_files']:
                        main_script = script
                        launch_command = f"streamlit run {script}"
                        launch_type = "streamlit_app"
                        confidence = 0.85
                        break
            
            # Gradio detection
            elif 'gradio' in req_text and 'app.py' in structure['python_files']:
                main_script = 'app.py'
                launch_command = "python app.py"
                launch_type = "gradio_app"
                confidence = 0.8
            
            # FastAPI detection
            elif 'fastapi' in req_text:
                for script in ['main.py', 'app.py', 'server.py']:
                    if script in structure['python_files']:
                        main_script = script
                        launch_command = f"uvicorn {script.replace('.py', '')}:app --host 0.0.0.0 --port 8000"
                        launch_type = "fastapi_app"
                        confidence = 0.8
                        break
            
            # Flask detection
            elif 'flask' in req_text:
                for script in ['app.py', 'main.py', 'server.py']:
                    if script in structure['python_files']:
                        main_script = script
                        launch_command = f"python {script}"
                        launch_type = "flask_app"
                        confidence = 0.75
                        break
        
        # 3. Docker detection
        if not main_script:
            if structure['docker_compose']:
                main_script = "docker-compose.yml"
                launch_command = "docker-compose up"
                launch_type = "docker_compose"
                confidence = 0.8
            elif structure['dockerfile']:
                main_script = "Dockerfile"
                launch_command = "docker build -t project . && docker run -it project"
                launch_type = "docker"
                confidence = 0.7
        
        # 4. Makefile detection
        if not main_script and structure['makefile']:
            main_script = "Makefile"
            launch_command = "make run"
            launch_type = "makefile"
            confidence = 0.7
        
        # 5. Any other shell scripts
        if not main_script and structure['executable_scripts']:
            main_script = structure['executable_scripts'][0]
            launch_command = f"./{main_script}"
            launch_type = "shell_script"
            confidence = 0.6
        elif not main_script and structure['scripts']:
            # Try shell scripts even if not marked as executable
            for script in structure['scripts']:
                if script.endswith('.sh'):
                    main_script = script
                    launch_command = f"./{script}"
                    launch_type = "shell_script"
                    confidence = 0.55
                    break
        
        # 6. Python scripts as last resort
        if not main_script:
            priority_python_scripts = ['app.py', 'main.py', 'run.py', 'start.py', 'launch.py', 'webui.py', 'server.py']
            
            for script in priority_python_scripts:
                if script in structure['python_files']:
                    main_script = script
                    launch_command = f"python {script}"
                    launch_type = "python_script"
                    confidence = 0.5
                    break
            
            # Check for nested scripts
            if not main_script:
                for py_file in structure['python_files']:
                    if '/' in py_file:
                        subdir, filename = py_file.split('/', 1)
                        if filename in priority_python_scripts:
                            main_script = py_file
                            launch_command = f"python {py_file}"
                            launch_type = "python_script"
                            confidence = 0.45
                            break
            
            # Use first Python file if nothing else found
            if not main_script and structure['python_files']:
                main_script = structure['python_files'][0]
                launch_command = f"python {main_script}"
                launch_type = "python_script"
                confidence = 0.3
        
        # Final fallback
        if not main_script:
            main_script = "unknown"
            launch_command = "echo 'No suitable launch method found'"
            launch_type = "unknown"
            confidence = 0.1
        
        # Always create custom launcher for fallback analysis too
        custom_launcher_path = self.create_custom_launcher_template(project_path, project_name, launch_command)
        
        return {
            'main_script': main_script,
            'launch_command': launch_command,
            'working_directory': '.',
            'requires_args': '',
            'launch_type': launch_type,
            'description': f"Launch {project_name} using {launch_type}",
            'confidence': confidence,
            'notes': f'Enhanced fallback heuristics - prioritized {launch_type}',
            'analysis_method': 'enhanced_fallback_heuristic',
            'model_used': 'none',
            'custom_launcher_path': custom_launcher_path,
            'analyzed_at': time.time()
        }

    def _fallback_analysis(self, structure: Dict, project_path: str, project_name: str, env_type: str, env_name: str) -> Dict:
        """Legacy fallback analysis - kept for compatibility"""
        return self._enhanced_fallback_analysis(structure, project_path, project_name, env_type, env_name)
    
    def analyze_complex_project(self, project_path: str, project_name: str) -> Dict:
        """Use the more powerful Qwen model for complex projects"""
        # This would be called for projects that the primary model couldn't handle well
        # or when we need more detailed analysis
        
        structure = self.analyze_project_structure(project_path)
        
        # Use more detailed prompt for complex analysis
        prompt = f"""You are an expert software architect analyzing a complex AI/ML project. This project requires detailed analysis to determine the best launch strategy.

Project: {project_name}
Path: {project_path}

Full Project Structure:
Python Files: {structure['python_files']}
Config Files: {structure['config_files']}
Requirements: {structure['requirements']}
Scripts: {structure['scripts']}
Directories: {structure['directories']}
Has Docker: {structure['dockerfile']} / {structure['docker_compose']}
Has Package.json: {structure['package_json']}
Has Makefile: {structure['makefile']}

README Content:
{structure['readme_content']}

This appears to be a complex project. Please provide a detailed analysis with multiple launch options if applicable.

Respond with JSON containing:
{{
    "primary_launch": {{
        "main_script": "primary entry point",
        "launch_command": "main launch command",
        "working_directory": ".",
        "launch_type": "type of application",
        "description": "what this launches"
    }},
    "alternative_launches": [
        {{
            "main_script": "alternative entry point",
            "launch_command": "alternative command",
            "description": "what this alternative does",
            "use_case": "when to use this option"
        }}
    ],
    "setup_required": "any setup steps needed before launch",
    "dependencies": "key dependencies or requirements",
    "notes": "important notes about this project",
    "confidence": 0.9
}}

Respond ONLY with valid JSON:"""
        
        response = self.call_qwen(self.advanced_model, prompt)
        
        if response:
            try:
                result = json.loads(response)
                result['analysis_method'] = 'qwen3_complex'
                result['model_used'] = self.advanced_model
                result['analyzed_at'] = time.time()
                return result
            except json.JSONDecodeError:
                pass
        
        # Fallback to regular analysis
        return self.generate_launch_command(project_path, project_name) 
    
    def _read_key_files(self, project_path: str, structure: Dict) -> str:
        """Read key files that might contain launch instructions"""
        path_obj = Path(project_path)
        content_parts = []
        
        # Read first few lines of shell scripts
        for script in structure['scripts'][:5]:
            script_path = path_obj / script
            if script_path.exists() and script_path.stat().st_size < 10000:
                try:
                    with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()[:10]
                        content_parts.append(f"\n--- {script} (first 10 lines) ---\n{''.join(lines)}")
                except:
                    pass
        
        # Read package.json scripts section
        if structure['package_json']:
            package_json_path = path_obj / 'package.json'
            try:
                with open(package_json_path, 'r', encoding='utf-8') as f:
                    package_data = json.loads(f.read())
                    if 'scripts' in package_data:
                        content_parts.append(f"\n--- package.json scripts ---\n{json.dumps(package_data['scripts'], indent=2)}")
            except:
                pass
        
        # Read Makefile
        if structure['makefile']:
            makefile_path = path_obj / 'Makefile'
            if not makefile_path.exists():
                makefile_path = path_obj / 'makefile'
            try:
                with open(makefile_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[:15]
                    content_parts.append(f"\n--- Makefile (first 15 lines) ---\n{''.join(lines)}")
            except:
                pass
        
        return ''.join(content_parts) if content_parts else "No key files found"
    
    def _clean_json_response(self, response: str) -> str:
        """Clean the AI response to extract valid JSON"""
        response_clean = response.strip()
        
        # Remove common markdown formatting
        if response_clean.startswith('```json'):
            response_clean = response_clean[7:]
        if response_clean.startswith('```'):
            response_clean = response_clean[3:]
        if response_clean.endswith('```'):
            response_clean = response_clean[:-3]
            
        # Find JSON object bounds
        start_idx = response_clean.find('{')
        end_idx = response_clean.rfind('}') + 1
        
        if start_idx >= 0 and end_idx > start_idx:
            response_clean = response_clean[start_idx:end_idx]
        
        return response_clean.strip() 