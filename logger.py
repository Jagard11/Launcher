import logging
import os
from datetime import datetime
from pathlib import Path

class AILauncherLogger:
    def __init__(self, log_file="ai_launcher.log"):
        self.log_file = log_file
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging configuration"""
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Full path for log file
        log_path = log_dir / self.log_file
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler()  # Also log to console
            ]
        )
        
        self.logger = logging.getLogger("AILauncher")
        self.ollama_logger = logging.getLogger("Ollama")
        
        # Set Ollama logger to be more verbose
        self.ollama_logger.setLevel(logging.DEBUG)
        
        # Create separate file handler for Ollama transactions
        ollama_handler = logging.FileHandler(log_dir / "ollama_transactions.log")
        ollama_formatter = logging.Formatter('%(asctime)s - OLLAMA - %(levelname)s - %(message)s')
        ollama_handler.setFormatter(ollama_formatter)
        self.ollama_logger.addHandler(ollama_handler)
    
    def info(self, message):
        """Log info message"""
        self.logger.info(message)
    
    def error(self, message):
        """Log error message"""
        self.logger.error(message)
    
    def warning(self, message):
        """Log warning message"""
        self.logger.warning(message)
    
    def debug(self, message):
        """Log debug message"""
        self.logger.debug(message)
    
    def ollama_request(self, model, prompt_preview):
        """Log Ollama request"""
        preview = prompt_preview[:200] + "..." if len(prompt_preview) > 200 else prompt_preview
        self.ollama_logger.info(f"REQUEST to {model}: {preview}")
    
    def ollama_response(self, model, response_preview, execution_time):
        """Log Ollama response"""
        preview = response_preview[:200] + "..." if len(response_preview) > 200 else response_preview
        self.ollama_logger.info(f"RESPONSE from {model} ({execution_time:.2f}s): {preview}")
    
    def ollama_error(self, model, error_message):
        """Log Ollama error"""
        self.ollama_logger.error(f"ERROR with {model}: {error_message}")
    
    def scan_progress(self, directory, found_count):
        """Log scanning progress"""
        self.logger.info(f"Scanning {directory}: found {found_count} projects so far")
    
    def launch_attempt(self, project_name, project_path, env_type):
        """Log launch attempt"""
        self.logger.info(f"Attempting to launch {project_name} at {project_path} with {env_type} environment")
    
    def launch_success(self, project_name):
        """Log successful launch"""
        self.logger.info(f"Successfully launched {project_name}")
    
    def launch_error(self, project_name, error_message):
        """Log launch error"""
        self.logger.error(f"Failed to launch {project_name}: {error_message}")

# Global logger instance
logger = AILauncherLogger() 