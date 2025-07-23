import threading
import time
import os
import uuid
from pathlib import Path
from typing import List, Dict, Callable, Optional
from queue import Queue
from concurrent.futures import ThreadPoolExecutor

from project_scanner import ProjectScanner
from environment_detector import EnvironmentDetector
from ollama_summarizer import OllamaSummarizer
from icon_generator import generate_project_icon
from project_database import db
from logger import logger

class BackgroundScanner:
    def __init__(self, config: dict, update_callback: Optional[Callable] = None):
        self.config = config
        self.update_callback = update_callback
        self.scanner = ProjectScanner(config['index_directories'])
        self.env_detector = EnvironmentDetector()
        self.summarizer = OllamaSummarizer()
        
        self.is_running = False
        self.scan_thread = None
        self.update_queue = Queue()
        
        # Scan intervals (in seconds)
        self.full_scan_interval = 3600  # 1 hour
        self.quick_scan_interval = 300   # 5 minutes
        
        self.last_full_scan = 0
        self.last_quick_scan = 0
        
    def start(self):
        """Start the background scanner"""
        if self.is_running:
            logger.warning("Background scanner is already running")
            return
        
        self.is_running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        logger.info("Background scanner started")
        
        # Start initial scan
        self.trigger_scan(scan_type='initial')
    
    def stop(self):
        """Stop the background scanner"""
        self.is_running = False
        if self.scan_thread and self.scan_thread.is_alive():
            self.scan_thread.join(timeout=5)
        logger.info("Background scanner stopped")
    
    def trigger_scan(self, scan_type: str = 'manual'):
        """Trigger an immediate scan"""
        self.update_queue.put(('scan', scan_type))
        logger.info(f"Triggered {scan_type} scan")
    
    def trigger_dirty_cleanup(self):
        """Trigger processing of dirty projects"""
        self.update_queue.put(('dirty', None))
        logger.info("Triggered dirty project cleanup")
    
    def _scan_loop(self):
        """Main scanning loop"""
        while self.is_running:
            try:
                current_time = time.time()
                
                # Check for manual triggers
                try:
                    while not self.update_queue.empty():
                        action, data = self.update_queue.get_nowait()
                        if action == 'scan':
                            self._perform_scan(scan_type=data)
                        elif action == 'dirty':
                            self._process_dirty_projects()
                except:
                    pass
                
                # Periodic scans
                if current_time - self.last_full_scan > self.full_scan_interval:
                    self._perform_scan(scan_type='full')
                    self.last_full_scan = current_time
                elif current_time - self.last_quick_scan > self.quick_scan_interval:
                    self._perform_scan(scan_type='quick')
                    self.last_quick_scan = current_time
                
                # Sleep for a bit
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in background scanner loop: {e}")
                time.sleep(30)  # Wait longer on error
    
    def _perform_scan(self, scan_type: str = 'full'):
        """Perform a directory scan"""
        session_id = f"{scan_type}_{uuid.uuid4().hex[:8]}"
        logger.info(f"Starting {scan_type} scan: {session_id}")
        
        try:
            # Start scan session
            db.start_scan_session(session_id, self.config['index_directories'])
            
            if scan_type == 'quick':
                # Quick scan: only check for new directories and verify existing ones
                projects_found, projects_updated = self._quick_scan()
            else:
                # Full scan: complete directory traversal
                projects_found, projects_updated = self._full_scan()
            
            # End scan session
            db.end_scan_session(session_id, projects_found, projects_updated)
            
            # Notify UI if callback provided
            if self.update_callback:
                try:
                    self.update_callback('scan_complete', {
                        'session_id': session_id,
                        'scan_type': scan_type,
                        'projects_found': projects_found,
                        'projects_updated': projects_updated
                    })
                except Exception as e:
                    logger.error(f"Error calling update callback: {e}")
            
        except Exception as e:
            logger.error(f"Error during {scan_type} scan: {e}")
    
    def _full_scan(self) -> tuple[int, int]:
        """Perform a full directory scan"""
        logger.info("Performing full directory scan...")
        
        # Get existing projects from database
        existing_projects = {p['path']: p for p in db.get_all_projects(active_only=False)}
        
        # Scan directories
        discovered_projects = self.scanner.scan_directories()
        
        projects_found = len(discovered_projects)
        projects_updated = 0
        current_paths = set()
        
        for project in discovered_projects:
            current_paths.add(project['path'])
            
            # Check if project exists in database
            existing = existing_projects.get(project['path'])
            
            if existing is None:
                # New project - add to database
                project_data = self._prepare_project_data(project)
                db.upsert_project(project_data)
                projects_updated += 1
                
                # Notify UI of new project
                if self.update_callback:
                    try:
                        self.update_callback('project_added', project_data)
                    except:
                        pass
                        
            else:
                # Existing project - check if needs update
                if self._should_update_project(existing, project):
                    project_data = self._prepare_project_data(project, existing)
                    db.upsert_project(project_data)
                    projects_updated += 1
                    
                    # Notify UI of project update
                    if self.update_callback:
                        try:
                            self.update_callback('project_updated', project_data)
                        except:
                            pass
        
        # Mark missing projects as inactive
        for path, existing in existing_projects.items():
            if path not in current_paths and existing['status'] == 'active':
                if not os.path.exists(path):
                    db.mark_project_inactive(path)
                    logger.info(f"Marked inactive: {existing['name']}")
        
        logger.info(f"Full scan complete: {projects_found} found, {projects_updated} updated")
        return projects_found, projects_updated
    
    def _quick_scan(self) -> tuple[int, int]:
        """Perform a quick scan - only check for new directories"""
        logger.info("Performing quick directory scan...")
        
        existing_paths = {p['path'] for p in db.get_all_projects()}
        new_projects = []
        
        # Only scan top-level directories for new additions
        for directory in self.config['index_directories']:
            if not os.path.exists(directory):
                continue
                
            try:
                for item in os.listdir(directory):
                    item_path = os.path.join(directory, item)
                    
                    if os.path.isdir(item_path) and not item.startswith('.'):
                        if item_path not in existing_paths:
                            # Check if it's an AI project
                            if (self.scanner.has_python_files(item_path) and 
                                self.scanner.is_ai_project(item_path)):
                                
                                actual_path = self.scanner.find_actual_project_path(item_path)
                                project = {
                                    'name': item,
                                    'path': actual_path,
                                    'is_git': self.scanner.is_git_repository(actual_path),
                                    'size': self.scanner.get_directory_size(actual_path)
                                }
                                new_projects.append(project)
                                
            except Exception as e:
                logger.error(f"Error during quick scan of {directory}: {e}")
        
        projects_updated = 0
        for project in new_projects:
            project_data = self._prepare_project_data(project)
            db.upsert_project(project_data)
            projects_updated += 1
            
            # Notify UI of new project
            if self.update_callback:
                try:
                    self.update_callback('project_added', project_data)
                except:
                    pass
        
        logger.info(f"Quick scan complete: {len(new_projects)} new projects found")
        return len(new_projects), projects_updated
    
    def _process_dirty_projects(self):
        """Process projects marked as dirty"""
        dirty_projects = db.get_dirty_projects()
        
        if not dirty_projects:
            logger.info("No dirty projects to process")
            return
        
        logger.info(f"Processing {len(dirty_projects)} dirty projects...")
        
        def process_single_project(project_data):
            try:
                path = project_data['path']
                name = project_data['name']
                
                # Generate AI summaries
                doc_summary = self.summarizer.summarize_documentation(path)
                code_summary = self.summarizer.summarize_code(path)
                tooltip, description = self.summarizer.generate_final_summary(
                    name, doc_summary, code_summary
                )
                
                # Update database
                update_data = {
                    'path': path,
                    'description': description,
                    'tooltip': tooltip,
                    'dirty_flag': 0,
                    'last_scanned': time.time()
                }
                
                db.upsert_project(update_data)
                logger.info(f"Processed dirty project: {name}")
                
                # Notify UI
                if self.update_callback:
                    self.update_callback('project_updated', update_data)
                    
            except Exception as e:
                logger.error(f"Error processing dirty project {project_data.get('name', 'Unknown')}: {e}")
        
        # Process dirty projects in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            executor.map(process_single_project, dirty_projects)
        
        logger.info(f"Completed processing {len(dirty_projects)} dirty projects")
    
    def _prepare_project_data(self, project: Dict, existing: Optional[Dict] = None) -> Dict:
        """Prepare project data for database storage"""
        # Detect environment
        env_info = self.env_detector.detect_environment(project['path'])
        
        # Generate icon
        icon_data = generate_project_icon(project['name'])
        
        # Find main script
        main_scripts = ['app.py', 'main.py', 'run.py', 'start.py', 'launch.py', 'webui.py']
        main_script = None
        
        for script in main_scripts:
            script_path = Path(project['path']) / script
            if script_path.exists():
                main_script = script
                break
        
        project_data = {
            'name': project['name'],
            'path': project['path'],
            'display_name': project['name'],
            'actual_path': project['path'],
            'environment_type': env_info['type'],
            'environment_name': env_info.get('name', ''),
            'main_script': main_script,
            'icon_data': icon_data,
            'size_mb': self._parse_size_to_mb(project.get('size', '0')),
            'is_git': project.get('is_git', False),
            'status': 'active',
            'dirty_flag': 1,  # Mark as dirty for AI processing
            'last_modified': time.time()
        }
        
        # If existing project, preserve some fields
        if existing:
            # Keep existing descriptions if not dirty
            if not existing.get('dirty_flag', True):
                project_data['description'] = existing.get('description', '')
                project_data['tooltip'] = existing.get('tooltip', '')
                project_data['dirty_flag'] = 0
        
        return project_data
    
    def _should_update_project(self, existing: Dict, current: Dict) -> bool:
        """Determine if a project should be updated"""
        # Check if path has changed (nested project detection)
        if existing.get('actual_path') != current['path']:
            return True
        
        # Check if directory was modified recently
        try:
            current_mtime = os.path.getmtime(current['path'])
            last_scanned = existing.get('last_scanned', 0)
            
            if isinstance(last_scanned, str):
                # Convert ISO string to timestamp if needed
                from datetime import datetime
                last_scanned = datetime.fromisoformat(last_scanned).timestamp()
            
            return current_mtime > last_scanned
        except:
            return False
    
    def _parse_size_to_mb(self, size_str: str) -> float:
        """Parse size string to MB"""
        if not size_str or size_str == 'Unknown':
            return 0.0
        
        try:
            size_str = size_str.strip().upper()
            if 'G' in size_str:
                return float(size_str.replace('G', '')) * 1024
            elif 'M' in size_str:
                return float(size_str.replace('M', ''))
            elif 'K' in size_str:
                return float(size_str.replace('K', '')) / 1024
            else:
                return float(size_str) / (1024 * 1024)  # Assume bytes
        except:
            return 0.0

# Global scanner instance
background_scanner = None

def get_scanner(config: dict, update_callback: Optional[Callable] = None) -> BackgroundScanner:
    """Get or create the global background scanner"""
    global background_scanner
    
    if background_scanner is None:
        background_scanner = BackgroundScanner(config, update_callback)
    
    return background_scanner 