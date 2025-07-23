import subprocess
import json
import os
import time
from pathlib import Path
from typing import Optional, Tuple
from logger import logger

class OllamaSummarizer:
    def __init__(self):
        self.doc_model = "granite3.1-dense:8b"  # Better for document summarization
        self.code_model = "granite-code:8b"     # Better for code analysis
        self.general_model = "granite3.1-dense:8b"  # For final summary generation
    
    def call_ollama(self, model: str, prompt: str) -> str:
        """Call Ollama with the specified model and prompt"""
        start_time = time.time()
        
        # Log the request
        logger.ollama_request(model, prompt)
        
        try:
            cmd = ['ollama', 'run', model, prompt]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)  # Increased timeout
            
            execution_time = time.time() - start_time
            
            if result.returncode == 0:
                response = result.stdout.strip()
                logger.ollama_response(model, response, execution_time)
                return response
            else:
                error_msg = f"Return code {result.returncode}: {result.stderr}"
                logger.ollama_error(model, error_msg)
                print(f"❌ Ollama error with {model}: {error_msg}")
                return ""
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            error_msg = f"Call timed out after {execution_time:.1f}s"
            logger.ollama_error(model, error_msg)
            print(f"⏱️ Ollama timeout with {model}: {error_msg}")
            return ""
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            logger.ollama_error(model, error_msg)
            print(f"💥 Ollama exception with {model}: {error_msg}")
            return ""
    
    def find_documentation_files(self, project_path: str) -> list:
        """Find documentation files in the project"""
        path_obj = Path(project_path)
        doc_files = []
        
        # Common documentation file patterns
        doc_patterns = [
            'README*', 'readme*', 'Read*',
            'INSTALL*', 'install*',
            'CHANGELOG*', 'changelog*',
            'CONTRIBUTING*', 'contributing*',
            'LICENSE*', 'license*',
            'USAGE*', 'usage*',
            'GUIDE*', 'guide*',
            '*.md', '*.rst', '*.txt'
        ]
        
        for pattern in doc_patterns:
            for file_path in path_obj.glob(pattern):
                if file_path.is_file() and file_path.stat().st_size < 100000:  # Max 100KB
                    doc_files.append(file_path)
        
        # Also check docs/ directory
        docs_dir = path_obj / 'docs'
        if docs_dir.exists():
            for file_path in docs_dir.rglob('*'):
                if file_path.is_file() and file_path.suffix in ['.md', '.rst', '.txt']:
                    if file_path.stat().st_size < 100000:
                        doc_files.append(file_path)
        
        return doc_files[:5]  # Limit to 5 files to avoid overwhelming the model
    
    def find_main_code_files(self, project_path: str) -> list:
        """Find main code files for analysis"""
        path_obj = Path(project_path)
        code_files = []
        
        # Priority files to analyze
        priority_files = ['app.py', 'main.py', 'run.py', 'start.py', '__init__.py']
        
        for priority_file in priority_files:
            file_path = path_obj / priority_file
            if file_path.exists() and file_path.stat().st_size < 50000:  # Max 50KB
                code_files.append(file_path)
        
        # If no priority files found, get some Python files
        if not code_files:
            for py_file in path_obj.glob('*.py'):
                if py_file.stat().st_size < 50000:
                    code_files.append(py_file)
                if len(code_files) >= 3:
                    break
        
        return code_files[:3]  # Limit to 3 files
    
    def summarize_documentation(self, project_path: str) -> str:
        """Summarize project documentation using granite model"""
        doc_files = self.find_documentation_files(project_path)
        
        if not doc_files:
            return "No documentation found."
        
        # Combine documentation content
        doc_content = ""
        for doc_file in doc_files:
            try:
                content = doc_file.read_text(encoding='utf-8', errors='ignore')
                doc_content += f"\n\n=== {doc_file.name} ===\n{content[:2000]}"  # Limit each file
            except Exception as e:
                print(f"Error reading {doc_file}: {e}")
                continue
        
        if not doc_content.strip():
            return "No readable documentation content found."
        
        prompt = f"""Please analyze the following project documentation and provide a concise summary of what this project does, its main features, and its purpose. Focus on the key functionality and user-facing features.

Documentation content:
{doc_content[:8000]}  

Provide a 2-3 sentence summary focusing on:
1. What the project does
2. Main features or capabilities
3. Target use case or audience

Summary:"""
        
        return self.call_ollama(self.doc_model, prompt)
    
    def summarize_code(self, project_path: str) -> str:
        """Summarize project code using granite code model"""
        code_files = self.find_main_code_files(project_path)
        
        if not code_files:
            return "No main code files found."
        
        # Combine code content
        code_content = ""
        for code_file in code_files:
            try:
                content = code_file.read_text(encoding='utf-8', errors='ignore')
                code_content += f"\n\n=== {code_file.name} ===\n{content[:3000]}"  # Limit each file
            except Exception as e:
                print(f"Error reading {code_file}: {e}")
                continue
        
        if not code_content.strip():
            return "No readable code content found."
        
        prompt = f"""Analyze the following Python code and provide a technical summary of what this application does. Focus on the main functionality, key libraries used, and the overall architecture or approach.

Code content:
{code_content[:10000]}

Provide a 2-3 sentence technical summary focusing on:
1. Main functionality and approach
2. Key technologies/libraries used
3. Type of application (web app, CLI tool, ML model, etc.)

Technical Summary:"""
        
        return self.call_ollama(self.code_model, prompt)
    
    def generate_final_summary(self, project_name: str, doc_summary: str, code_summary: str) -> Tuple[str, str]:
        """Generate final tooltip and description combining both summaries"""
        
        combined_info = f"""
Project Name: {project_name}

Documentation Summary: {doc_summary}

Code Analysis: {code_summary}
"""
        
        # Generate tooltip (short)
        tooltip_prompt = f"""Based on the following project information, create a very brief tooltip (1 sentence, max 80 characters) that describes what this AI/ML project does:

{combined_info}

Tooltip (1 sentence, max 80 chars):"""
        
        tooltip = self.call_ollama(self.general_model, tooltip_prompt)
        
        # Generate description (longer)
        description_prompt = f"""Based on the following project information, create a comprehensive but concise description (2-4 sentences) of this AI/ML project. Include what it does, how it works, and what makes it useful:

{combined_info}

Description (2-4 sentences):"""
        
        description = self.call_ollama(self.general_model, description_prompt)
        
        # Fallbacks if Ollama fails
        if not tooltip.strip():
            tooltip = f"AI project: {project_name}"
        
        if not description.strip():
            description = f"AI/ML project located at {project_name}. " + (doc_summary or code_summary or "No description available.")
        
        return tooltip.strip()[:80], description.strip()  # Ensure tooltip length limit 