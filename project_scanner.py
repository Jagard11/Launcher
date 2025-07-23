import os
import subprocess
from pathlib import Path
from typing import List, Dict
from logger import logger

class ProjectScanner:
    def __init__(self, index_directories: List[str]):
        self.index_directories = index_directories
    
    def is_git_repository(self, path: str) -> bool:
        """Check if a directory is a git repository"""
        git_dir = Path(path) / '.git'
        return git_dir.exists()
    
    def has_python_files(self, path: str) -> bool:
        """Check if directory contains Python files"""
        path_obj = Path(path)
        
        # Check for common Python files
        python_files = list(path_obj.glob('*.py'))
        if python_files:
            return True
            
        # Check in subdirectories (but not too deep)
        for subdir in path_obj.iterdir():
            if subdir.is_dir() and not subdir.name.startswith('.'):
                python_files = list(subdir.glob('*.py'))
                if python_files:
                    return True
        
        return False
    
    def is_ai_project(self, path: str) -> bool:
        """Heuristic to determine if this is likely an AI/ML project"""
        path_obj = Path(path)
        
        # Check for AI-related files
        ai_indicators = [
            'requirements.txt', 'environment.yml', 'conda.yaml',
            'app.py', 'main.py', 'train.py', 'model.py',
            'Dockerfile', 'docker-compose.yml'
        ]
        
        ai_keywords = [
            'torch', 'tensorflow', 'gradio', 'streamlit', 'flask',
            'fastapi', 'transformers', 'diffusers', 'stable',
            'comfy', 'automatic', 'ai', 'ml', 'neural', 'model',
            'llm', 'whisper', 'voice', 'speech', 'vision', 'image',
            'video', 'generation', 'training', 'inference', 'dataset',
            'kohya', 'webui', 'diffusion', 'text-generation',
            'embedding', 'retrieval', 'chatbot', 'assistant'
        ]
        
        # Check for indicator files
        for indicator in ai_indicators:
            if (path_obj / indicator).exists():
                return True
        
        # Check directory name for AI keywords
        dir_name = path_obj.name.lower()
        for keyword in ai_keywords:
            if keyword in dir_name:
                return True
        
        # Check requirements.txt content
        req_file = path_obj / 'requirements.txt'
        if req_file.exists():
            try:
                content = req_file.read_text().lower()
                for keyword in ai_keywords:
                    if keyword in content:
                        return True
            except:
                pass
        
        return False
    
    def scan_directory(self, directory: str) -> List[Dict]:
        """Scan a single directory for AI projects"""
        projects = []
        
        if not os.path.exists(directory):
            logger.warning(f"Directory {directory} does not exist")
            return projects
        
        logger.info(f"Starting scan of directory: {directory}")
        
        try:
            items = os.listdir(directory)
            logger.info(f"Found {len(items)} items in {directory}")
            
            for i, item in enumerate(items):
                item_path = os.path.join(directory, item)
                
                if os.path.isdir(item_path):
                    # Skip hidden directories
                    if item.startswith('.'):
                        logger.debug(f"Skipping hidden directory: {item}")
                        continue
                    
                    logger.debug(f"Checking directory {i+1}/{len(items)}: {item}")
                    
                    # Check if it's a potential AI project
                    if self.has_python_files(item_path):
                        logger.debug(f"Found Python files in: {item}")
                        if self.is_ai_project(item_path):
                            logger.info(f"✅ Identified AI project: {item}")
                            
                            # Check for nested projects and use the most specific one
                            actual_project_path = self.find_actual_project_path(item_path)
                            
                            project_info = {
                                'name': item,
                                'path': actual_project_path,
                                'is_git': self.is_git_repository(actual_project_path),
                                'size': self.get_directory_size(actual_project_path)
                            }
                            projects.append(project_info)
                            
                            # Log progress every 10 projects
                            if len(projects) % 10 == 0:
                                logger.scan_progress(directory, len(projects))
                        else:
                            logger.debug(f"Has Python files but not AI project: {item}")
                    else:
                        logger.debug(f"No Python files found in: {item}")
        
        except PermissionError:
            logger.error(f"Permission denied accessing {directory}")
        except Exception as e:
            logger.error(f"Error scanning {directory}: {e}")
        
        logger.info(f"Completed scan of {directory}: found {len(projects)} AI projects")
        return projects
    
    def find_actual_project_path(self, path: str) -> str:
        """Find the actual project path, looking for nested main applications"""
        path_obj = Path(path)
        
        # First check if there are main scripts in the current directory
        main_scripts = ['app.py', 'main.py', 'run.py', 'start.py', 'launch.py', 'webui.py']
        current_scripts = [script for script in main_scripts if (path_obj / script).exists()]
        
        if current_scripts:
            logger.debug(f"Found main scripts in {path}: {current_scripts}")
            return path
        
        # Look for subdirectories that might contain the actual application
        subdirs = [item for item in path_obj.iterdir() if item.is_dir() and not item.name.startswith('.')]
        
        for subdir in subdirs:
            subdir_scripts = [script for script in main_scripts if (subdir / script).exists()]
            if subdir_scripts:
                logger.info(f"Found nested project in {subdir}: {subdir_scripts}")
                return str(subdir)
        
        # If no nested project found, return original path
        return path
    
    def get_directory_size(self, path: str) -> str:
        """Get human readable directory size"""
        try:
            result = subprocess.run(['du', '-sh', path], 
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return result.stdout.split()[0]
        except:
            pass
        return "Unknown"
    
    def scan_directories(self) -> List[Dict]:
        """Scan all indexed directories for AI projects"""
        all_projects = []
        
        logger.info(f"Starting scan of {len(self.index_directories)} directories")
        
        for directory in self.index_directories:
            logger.info(f"🔍 Scanning {directory}...")
            projects = self.scan_directory(directory)
            all_projects.extend(projects)
            logger.info(f"📊 Found {len(projects)} projects in {directory}")
        
        # Sort by name
        all_projects.sort(key=lambda x: x['name'].lower())
        
        logger.info(f"🎯 Total projects found: {len(all_projects)}")
        print(f"🎯 Total projects found: {len(all_projects)}")
        return all_projects 