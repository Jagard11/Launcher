#!/usr/bin/env python3

import subprocess
import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, List
from logger import logger

class QwenLaunchAnalyzer:
    def __init__(self):
        # Use the available Qwen3 models - prefer smaller ones for speed
        self.primary_model = "qwen3:8b"         # Fast and efficient for most analysis
        self.advanced_model = "qwen3:14b"       # For complex projects
        self.fallback_model = "qwen3:8b"        # Fallback option
        
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
    
    def analyze_project_structure(self, project_path: str) -> Dict:
        """Analyze project structure to understand its layout"""
        path_obj = Path(project_path)
        
        structure = {
            'python_files': [],
            'config_files': [],
            'requirements': [],
            'scripts': [],
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
            
            # Get script files
            script_patterns = ['*.sh', '*.bat', 'launch*', 'run*', 'start*']
            for pattern in script_patterns:
                for script_file in path_obj.glob(pattern):
                    if script_file.is_file():
                        structure['scripts'].append(script_file.name)
        
        except Exception as e:
            logger.error(f"Error analyzing project structure for {project_path}: {e}")
        
        return structure
    
    def generate_launch_command(self, project_path: str, project_name: str, env_type: str = "none", env_name: str = "") -> Dict:
        """Generate intelligent launch command using Qwen3"""
        structure = self.analyze_project_structure(project_path)
        
        # Create context for the AI
        context = f"""
Project Analysis for: {project_name}
Location: {project_path}
Environment: {env_type} ({env_name})

Python Files Found: {structure['python_files'][:10]}
Configuration Files: {structure['config_files']}
Requirements: {structure['requirements'][:10]}
Script Files: {structure['scripts']}
Directories: {structure['directories'][:10]}
Has Dockerfile: {structure['dockerfile']}
Has Docker Compose: {structure['docker_compose']}
Has Package.json: {structure['package_json']}
Has Makefile: {structure['makefile']}

README Content (first 1000 chars):
{structure['readme_content'][:1000]}
"""
        
        prompt = f"""Analyze this software project structure and determine the best launch command.

{context}

Respond with ONLY valid JSON in this exact format (no thinking, no explanations, just JSON):
{{
    "main_script": "primary script file name",
    "launch_command": "exact command to run",
    "working_directory": ".",
    "requires_args": "",
    "launch_type": "python_script",
    "description": "brief description",
    "confidence": 0.8,
    "notes": "any notes"
}}

Rules:
- app.py, main.py, run.py, start.py, webui.py are main entry points
- For Gradio: python app.py
- For Streamlit: streamlit run app.py  
- For Docker: use docker commands
- Choose highest confidence option
- Return ONLY JSON, no other text or tags"""

        # Try to get response from Qwen
        response = self.call_qwen(self.primary_model, prompt)
        
        if not response:
            # Fallback to simpler analysis
            return self._fallback_analysis(structure, project_path, project_name, env_type, env_name)
        
        try:
            # Clean the response - remove thinking tags and extract JSON
            cleaned_response = self._extract_json_from_response(response)
            
            # Parse JSON response
            result = json.loads(cleaned_response)
            
            # Validate required fields
            required_fields = ['main_script', 'launch_command', 'working_directory', 'launch_type', 'confidence']
            if not all(field in result for field in required_fields):
                logger.warning(f"Qwen response missing required fields for {project_name}, using fallback")
                return self._fallback_analysis(structure, project_path, project_name, env_type, env_name)
            
            # Add metadata
            result['analysis_method'] = 'qwen3_ai'
            result['model_used'] = self.primary_model
            result['analyzed_at'] = time.time()
            
            logger.info(f"Generated AI launch command for {project_name}: {result['launch_command']}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Qwen JSON response for {project_name}: {e}")
            logger.debug(f"Raw response: {response[:500]}...")
            return self._fallback_analysis(structure, project_path, project_name, env_type, env_name)
    
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
    
    def _fallback_analysis(self, structure: Dict, project_path: str, project_name: str, env_type: str, env_name: str) -> Dict:
        """Fallback analysis when AI fails"""
        logger.info(f"Using fallback analysis for {project_name}")
        
        # Priority order for main scripts
        priority_scripts = ['app.py', 'main.py', 'run.py', 'start.py', 'launch.py', 'webui.py', 'server.py']
        
        main_script = None
        launch_type = "python_script"
        
        # Find the best main script
        for script in priority_scripts:
            if script in structure['python_files']:
                main_script = script
                break
        
        # Check for nested scripts
        if not main_script:
            for py_file in structure['python_files']:
                if '/' in py_file:
                    subdir, filename = py_file.split('/', 1)
                    if filename in priority_scripts:
                        main_script = py_file
                        break
        
        # If no priority script found, use first Python file
        if not main_script and structure['python_files']:
            main_script = structure['python_files'][0]
        
        # Determine launch type based on structure
        if any('gradio' in req.lower() for req in structure['requirements']):
            launch_type = "gradio_app"
        elif any('streamlit' in req.lower() for req in structure['requirements']):
            launch_type = "streamlit_app"
        elif any('flask' in req.lower() for req in structure['requirements']):
            launch_type = "flask_app"
        elif any('fastapi' in req.lower() for req in structure['requirements']):
            launch_type = "fastapi_app"
        elif structure['dockerfile'] or structure['docker_compose']:
            launch_type = "docker"
        elif structure['makefile']:
            launch_type = "makefile"
        elif structure['scripts']:
            launch_type = "shell_script"
            main_script = structure['scripts'][0]
        
        # Generate launch command
        if not main_script:
            launch_command = "echo 'No main script found'"
            confidence = 0.1
        elif launch_type == "streamlit_app":
            launch_command = f"streamlit run {main_script}"
            confidence = 0.8
        elif launch_type == "docker":
            if structure['docker_compose']:
                launch_command = "docker-compose up"
            else:
                launch_command = "docker build -t project . && docker run -p 8080:8080 project"
            confidence = 0.7
        elif launch_type == "makefile":
            launch_command = "make run"
            confidence = 0.6
        elif launch_type == "shell_script":
            launch_command = f"bash {main_script}"
            confidence = 0.6
        else:
            launch_command = f"python3 {main_script}"
            confidence = 0.7
        
        return {
            'main_script': main_script or 'unknown',
            'launch_command': launch_command,
            'working_directory': '.',
            'requires_args': '',
            'launch_type': launch_type,
            'description': f"Launch {project_name} using {launch_type}",
            'confidence': confidence,
            'notes': 'Generated using fallback heuristics',
            'analysis_method': 'fallback_heuristic',
            'model_used': 'none',
            'analyzed_at': time.time()
        }
    
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