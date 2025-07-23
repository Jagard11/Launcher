import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

class EnvironmentDetector:
    def __init__(self):
        pass
    
    def detect_conda_env(self, project_path: str) -> Optional[Dict]:
        """Detect conda environment for the project"""
        path_obj = Path(project_path)
        
        # Check for environment.yml or conda.yaml
        conda_files = ['environment.yml', 'environment.yaml', 'conda.yml', 'conda.yaml']
        for conda_file in conda_files:
            conda_path = path_obj / conda_file
            if conda_path.exists():
                try:
                    # Try to extract environment name from file
                    content = conda_path.read_text()
                    lines = content.split('\n')
                    for line in lines:
                        if line.strip().startswith('name:'):
                            env_name = line.split(':', 1)[1].strip()
                            return {
                                'type': 'conda',
                                'name': env_name,
                                'config_file': str(conda_path)
                            }
                except:
                    pass
        
        # Check if there's a conda environment with the same name as the project
        project_name = path_obj.name
        try:
            result = subprocess.run(['conda', 'env', 'list'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if project_name in line and not line.strip().startswith('#'):
                        return {
                            'type': 'conda',
                            'name': project_name,
                            'config_file': None
                        }
        except:
            pass
        
        return None
    
    def detect_venv(self, project_path: str) -> Optional[Dict]:
        """Detect virtual environment for the project"""
        path_obj = Path(project_path)
        
        # Common venv directory names
        venv_names = ['venv', 'env', '.env', '.venv', 'virtualenv']
        
        for venv_name in venv_names:
            venv_path = path_obj / venv_name
            if venv_path.exists() and venv_path.is_dir():
                # Check for activation script
                activate_paths = [
                    venv_path / 'bin' / 'activate',  # Unix
                    venv_path / 'Scripts' / 'activate'  # Windows
                ]
                
                for activate_path in activate_paths:
                    if activate_path.exists():
                        return {
                            'type': 'venv',
                            'name': venv_name,
                            'path': str(venv_path),
                            'activate_path': str(activate_path)
                        }
        
        return None
    
    def detect_poetry(self, project_path: str) -> Optional[Dict]:
        """Detect Poetry environment"""
        path_obj = Path(project_path)
        pyproject_path = path_obj / 'pyproject.toml'
        
        if pyproject_path.exists():
            try:
                content = pyproject_path.read_text()
                if '[tool.poetry]' in content:
                    return {
                        'type': 'poetry',
                        'name': 'poetry-env',
                        'config_file': str(pyproject_path)
                    }
            except:
                pass
        
        return None
    
    def detect_pipenv(self, project_path: str) -> Optional[Dict]:
        """Detect Pipenv environment"""
        path_obj = Path(project_path)
        pipfile_path = path_obj / 'Pipfile'
        
        if pipfile_path.exists():
            return {
                'type': 'pipenv',
                'name': 'pipenv-env',
                'config_file': str(pipfile_path)
            }
        
        return None
    
    def detect_requirements(self, project_path: str) -> Optional[Dict]:
        """Check for requirements.txt (fallback to system Python)"""
        path_obj = Path(project_path)
        req_path = path_obj / 'requirements.txt'
        
        if req_path.exists():
            return {
                'type': 'requirements',
                'name': 'system-python',
                'config_file': str(req_path)
            }
        
        return None
    
    def detect_environment(self, project_path: str) -> Dict:
        """Detect the Python environment for a project"""
        
        # Try different environment detection methods in order of preference
        detectors = [
            self.detect_conda_env,
            self.detect_venv,
            self.detect_poetry,
            self.detect_pipenv,
            self.detect_requirements
        ]
        
        for detector in detectors:
            result = detector(project_path)
            if result:
                return result
        
        # No environment detected
        return {
            'type': 'none',
            'name': 'No environment detected',
            'config_file': None
        }
    
    def get_python_version(self, project_path: str) -> str:
        """Get Python version for the project environment"""
        env_info = self.detect_environment(project_path)
        
        try:
            if env_info['type'] == 'conda':
                result = subprocess.run(['conda', 'run', '-n', env_info['name'], 'python', '--version'],
                                      capture_output=True, text=True, timeout=10)
            elif env_info['type'] == 'venv':
                python_path = Path(env_info['path']) / 'bin' / 'python'
                result = subprocess.run([str(python_path), '--version'],
                                      capture_output=True, text=True, timeout=10)
            else:
                result = subprocess.run(['python', '--version'],
                                      capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        
        return "Unknown" 