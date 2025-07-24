import gradio as gr
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from logger import logger

DEFAULT_CONFIG = {
    "index_directories": []
}

class SettingsManager:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load configuration from config.json with fallback to defaults"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    # Ensure required keys exist
                    for key, default_value in DEFAULT_CONFIG.items():
                        if key not in config:
                            config[key] = default_value
                    return config
            else:
                logger.warning(f"Config file {self.config_path} not found, using defaults")
                return DEFAULT_CONFIG.copy()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return DEFAULT_CONFIG.copy()
    
    def save_config(self, config: Dict) -> bool:
        """Save configuration to config.json"""
        try:
            # Validate config structure
            if not isinstance(config.get('index_directories'), list):
                raise ValueError("index_directories must be a list")
            
            # Create backup if file exists
            if os.path.exists(self.config_path):
                backup_path = f"{self.config_path}.backup"
                with open(self.config_path, 'r') as src, open(backup_path, 'w') as dst:
                    dst.write(src.read())
                logger.info(f"Created backup: {backup_path}")
            
            # Save new config
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            self.config = config
            logger.info("Configuration saved successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False
    
    def add_directory(self, directory_path: str) -> tuple[bool, str]:
        """Add a directory to index_directories"""
        try:
            directory_path = str(Path(directory_path).resolve())
            
            # Validate directory exists
            if not os.path.exists(directory_path):
                return False, f"Directory does not exist: {directory_path}"
            
            if not os.path.isdir(directory_path):
                return False, f"Path is not a directory: {directory_path}"
            
            # Check if already exists
            if directory_path in self.config['index_directories']:
                return False, f"Directory already in index: {directory_path}"
            
            # Add directory
            new_config = self.config.copy()
            new_config['index_directories'].append(directory_path)
            
            if self.save_config(new_config):
                # Mark all existing projects as dirty to force re-analysis
                self._mark_all_projects_dirty()
                return True, f"Added directory: {directory_path}"
            else:
                return False, "Failed to save configuration"
                
        except Exception as e:
            return False, f"Error adding directory: {str(e)}"
    
    def remove_directory(self, directory_path: str) -> tuple[bool, str]:
        """Remove a directory from index_directories"""
        try:
            directory_path = str(Path(directory_path).resolve())
            
            if directory_path not in self.config['index_directories']:
                return False, f"Directory not in index: {directory_path}"
            
            # Remove directory
            new_config = self.config.copy()
            new_config['index_directories'].remove(directory_path)
            
            if self.save_config(new_config):
                # Mark affected projects as needing cleanup
                self._mark_removed_directory_projects(directory_path)
                return True, f"Removed directory: {directory_path}"
            else:
                return False, "Failed to save configuration"
                
        except Exception as e:
            return False, f"Error removing directory: {str(e)}"
    
    def _mark_removed_directory_projects(self, removed_directory: str):
        """Mark projects from removed directory as inactive and clean up custom launchers"""
        try:
            from project_database import db
            
            # Get all projects under the removed directory
            all_projects = db.get_all_projects(active_only=False)
            affected_projects = []
            
            for project in all_projects:
                project_path = Path(project['path'])
                removed_path = Path(removed_directory)
                
                # Check if project is under the removed directory
                try:
                    project_path.relative_to(removed_path)
                    affected_projects.append(project)
                except ValueError:
                    # Not under removed directory
                    continue
            
            if affected_projects:
                logger.info(f"Cleaning up {len(affected_projects)} projects from removed directory: {removed_directory}")
                
                for project in affected_projects:
                    # Mark project as inactive
                    db.mark_project_inactive(project['path'])
                    
                    # Remove custom launcher if exists
                    project_name = project['name']
                    safe_name = "".join(c for c in project_name if c.isalnum() or c in ('-', '_')).strip()
                    custom_launcher_path = Path("custom_launchers") / f"{safe_name}.sh"
                    
                    if custom_launcher_path.exists():
                        try:
                            custom_launcher_path.unlink()
                            logger.info(f"Removed custom launcher: {custom_launcher_path}")
                        except Exception as e:
                            logger.error(f"Failed to remove custom launcher {custom_launcher_path}: {e}")
                
                logger.info(f"Cleanup completed for directory: {removed_directory}")
            
        except Exception as e:
            logger.error(f"Error cleaning up removed directory projects: {e}")
    
    def _mark_all_projects_dirty(self):
        """Mark all projects as dirty when configuration changes significantly"""
        try:
            from project_database import db
            
            # Get count of projects before marking dirty
            all_projects = db.get_all_projects(active_only=True)
            project_count = len(all_projects)
            
            if project_count > 0:
                # Mark all projects as dirty for re-analysis
                import sqlite3
                conn = sqlite3.connect(db.db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE projects SET dirty_flag = 1 WHERE status = 'active'")
                updated_count = cursor.rowcount
                conn.commit()
                conn.close()
                
                logger.info(f"Marked {updated_count} projects as dirty due to directory configuration change")
            
        except Exception as e:
            logger.error(f"Error marking projects as dirty: {e}")
    
    def validate_directories(self) -> List[str]:
        """Validate all configured directories and return issues"""
        issues = []
        
        for directory in self.config['index_directories']:
            if not os.path.exists(directory):
                issues.append(f"Directory does not exist: {directory}")
            elif not os.path.isdir(directory):
                issues.append(f"Path is not a directory: {directory}")
            elif not os.access(directory, os.R_OK):
                issues.append(f"Directory not readable: {directory}")
        
        return issues

def build_settings_ui():
    """Build the settings UI tab"""
    settings_manager = SettingsManager()
    
    # Initialize display data
    directories = settings_manager.config.get('index_directories', [])
    issues = settings_manager.validate_directories()
    
    with gr.Column() as settings_content:
        gr.Markdown("## ⚙️ Configuration Settings")
        gr.Markdown("Manage directories to index for AI projects and configure launcher behavior.")
        
        # Configuration Status
        initial_status = f"**Status:** {len(directories)} directories configured"
        if issues:
            initial_status += f" • {len(issues)} issues found"
        
        with gr.Row():
            config_status = gr.Markdown(initial_status)
        
        # Directory Management Section
        gr.Markdown("### 📁 Indexed Directories")
        gr.Markdown("Configure which directories should be scanned for AI projects.")
        
        # Create initial display data
        initial_data = []
        for directory in directories:
            status = "❌ Issue" if any(directory in issue for issue in issues) else "✅ OK"
            initial_data.append([directory, status])
        
        # Current directories display
        current_directories = gr.Dataframe(
            headers=["Directory Path", "Status"],
            datatype=["str", "str"],
            label="Currently Indexed Directories",
            interactive=False,
            wrap=True,
            value=initial_data
        )
        
        # Add directory section
        with gr.Row():
            with gr.Column(scale=3):
                new_directory_input = gr.Textbox(
                    label="Add Directory",
                    placeholder="/path/to/your/ai/projects",
                    info="Enter the full path to a directory containing AI projects"
                )
            with gr.Column(scale=1):
                add_directory_btn = gr.Button("➕ Add Directory", variant="primary")
        
        # Remove directory section
        with gr.Row():
            with gr.Column(scale=3):
                remove_directory_input = gr.Textbox(
                    label="Remove Directory",
                    placeholder="Select a directory path to remove",
                    info="Enter the full path of a directory to remove from indexing"
                )
            with gr.Column(scale=1):
                remove_directory_btn = gr.Button("➖ Remove Directory", variant="secondary")
        
        # Actions output
        settings_output = gr.Textbox(
            label="Actions Output",
            interactive=False,
            lines=3,
            placeholder="Directory management results will appear here..."
        )
        
        # Advanced Settings Section
        with gr.Accordion("🔧 Advanced Settings", open=False):
            gr.Markdown("### Raw Configuration Editor")
            gr.Markdown("⚠️ **Warning:** Direct editing of configuration JSON. Invalid JSON will be rejected.")
            
            config_editor = gr.Textbox(
                label="config.json Content",
                lines=10,
                placeholder="Configuration will be loaded here...",
                info="Edit the raw JSON configuration. Changes are validated before saving."
            )
            
            with gr.Row():
                load_config_btn = gr.Button("📥 Load Current Config")
                save_config_btn = gr.Button("💾 Save Config", variant="primary")
                reset_config_btn = gr.Button("🔄 Reset to Defaults", variant="secondary")
        
        # Validation Section
        gr.Markdown("### ✅ Configuration Validation")
        validation_output = gr.Markdown("Click 'Validate Configuration' to check for issues.")
        
        validate_btn = gr.Button("🔍 Validate Configuration", variant="secondary")
        
        # Helper functions for UI interactions
        def refresh_directories_display():
            """Refresh the directories display"""
            settings_manager.config = settings_manager.load_config()  # Reload from file
            directories = settings_manager.config.get('index_directories', [])
            issues = settings_manager.validate_directories()
            
            # Create display data
            display_data = []
            for directory in directories:
                status = "❌ Issue" if any(directory in issue for issue in issues) else "✅ OK"
                display_data.append([directory, status])
            
            # Status message
            status_msg = f"**Status:** {len(directories)} directories configured"
            if issues:
                status_msg += f" • {len(issues)} issues found"
            
            return display_data, status_msg
        
        def handle_add_directory(directory_path):
            """Handle adding a new directory"""
            if not directory_path.strip():
                return refresh_directories_display()[0], refresh_directories_display()[1], "❌ Please enter a directory path"
            
            success, message = settings_manager.add_directory(directory_path.strip())
            
            if success:
                # Trigger background scan for new directory
                try:
                    from background_scanner import get_scanner
                    scanner = get_scanner()
                    if scanner:
                        scanner.trigger_scan(scan_type='directory_added')
                        message += " • Background scan initiated"
                except Exception as e:
                    message += f" • Warning: Failed to trigger scan: {str(e)}"
            
            # Refresh display
            display_data, status_msg = refresh_directories_display()
            return display_data, status_msg, message
        
        def handle_remove_directory(directory_path):
            """Handle removing a directory"""
            if not directory_path.strip():
                return refresh_directories_display()[0], refresh_directories_display()[1], "❌ Please enter a directory path"
            
            success, message = settings_manager.remove_directory(directory_path.strip())
            
            # Refresh display
            display_data, status_msg = refresh_directories_display()
            return display_data, status_msg, message
        
        def handle_load_config():
            """Load current config into editor"""
            try:
                with open(settings_manager.config_path, 'r') as f:
                    content = f.read()
                return content
            except Exception as e:
                return f"Error loading config: {str(e)}"
        
        def handle_save_config(config_content):
            """Save config from editor"""
            try:
                # Validate JSON
                config = json.loads(config_content)
                
                # Validate structure
                if not isinstance(config.get('index_directories'), list):
                    return "❌ Error: 'index_directories' must be a list"
                
                # Save config
                if settings_manager.save_config(config):
                    # Refresh display
                    return "✅ Configuration saved successfully"
                else:
                    return "❌ Failed to save configuration"
                    
            except json.JSONDecodeError as e:
                return f"❌ Invalid JSON: {str(e)}"
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def handle_reset_config():
            """Reset config to defaults"""
            if settings_manager.save_config(DEFAULT_CONFIG.copy()):
                return json.dumps(DEFAULT_CONFIG, indent=2), "✅ Configuration reset to defaults"
            else:
                return gr.update(), "❌ Failed to reset configuration"
        
        def handle_validate_config():
            """Validate current configuration"""
            settings_manager.config = settings_manager.load_config()  # Reload
            issues = settings_manager.validate_directories()
            
            if not issues:
                return "✅ **Configuration Valid:** All directories are accessible and properly configured."
            else:
                issues_text = "\n".join([f"• {issue}" for issue in issues])
                return f"⚠️ **Configuration Issues Found:**\n\n{issues_text}"
        
        # Wire up event handlers
        add_directory_btn.click(
            handle_add_directory,
            inputs=[new_directory_input],
            outputs=[current_directories, config_status, settings_output]
        )
        
        remove_directory_btn.click(
            handle_remove_directory,
            inputs=[remove_directory_input],
            outputs=[current_directories, config_status, settings_output]
        )
        
        load_config_btn.click(
            handle_load_config,
            outputs=[config_editor]
        )
        
        save_config_btn.click(
            handle_save_config,
            inputs=[config_editor],
            outputs=[settings_output]
        )
        
        reset_config_btn.click(
            handle_reset_config,
            outputs=[config_editor, settings_output]
        )
        
        validate_btn.click(
            handle_validate_config,
            outputs=[validation_output]
        )
        
        # Initialize display when tab loads (handled by parent app)
        # The initialization will be triggered when the settings tab becomes visible
    
    return settings_content

def config_exists() -> bool:
    """Check if config.json exists"""
    return os.path.exists("config.json")

def create_default_config() -> bool:
    """Create a default config.json file"""
    try:
        settings_manager = SettingsManager()
        return settings_manager.save_config(DEFAULT_CONFIG.copy())
    except Exception as e:
        logger.error(f"Failed to create default config: {e}")
        return False 