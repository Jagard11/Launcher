import sqlite3
import json
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from logger import logger

class ProjectDatabase:
    def __init__(self, db_path: str = "projects.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Projects table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT UNIQUE NOT NULL,
                display_name TEXT,
                actual_path TEXT,
                environment_type TEXT,
                environment_name TEXT,
                main_script TEXT,
                description TEXT,
                tooltip TEXT,
                icon_data TEXT,
                size_mb REAL,
                is_git BOOLEAN,
                status TEXT DEFAULT 'active',
                dirty_flag BOOLEAN DEFAULT 1,
                last_scanned TIMESTAMP,
                last_modified TIMESTAMP,
                scan_duration REAL,
                launch_command TEXT,
                launch_type TEXT,
                launch_working_directory TEXT,
                launch_args TEXT,
                launch_confidence REAL,
                launch_notes TEXT,
                launch_analysis_method TEXT,
                launch_analyzed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Scan sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                projects_found INTEGER,
                projects_updated INTEGER,
                directories_scanned TEXT,
                status TEXT DEFAULT 'running'
            )
        ''')
        
        # Project tags table (for future extensibility)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                tag TEXT,
                FOREIGN KEY (project_id) REFERENCES projects (id)
            )
        ''')
        
        # Add launch command columns to existing projects table if they don't exist
        cursor.execute("PRAGMA table_info(projects)")
        columns = [col[1] for col in cursor.fetchall()]
        
        launch_columns = [
            ('launch_command', 'TEXT'),
            ('launch_type', 'TEXT'),
            ('launch_working_directory', 'TEXT'),
            ('launch_args', 'TEXT'),
            ('launch_confidence', 'REAL'),
            ('launch_notes', 'TEXT'),
            ('launch_analysis_method', 'TEXT'),
            ('launch_analyzed_at', 'TIMESTAMP'),
            ('is_favorite', 'BOOLEAN DEFAULT 0'),
            ('is_hidden', 'BOOLEAN DEFAULT 0')
        ]
        
        for col_name, col_type in launch_columns:
            if col_name not in columns:
                cursor.execute(f'ALTER TABLE projects ADD COLUMN {col_name} {col_type}')
                logger.info(f"Added column {col_name} to projects table")
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")
    
    def get_project_by_path(self, path: str) -> Optional[Dict]:
        """Get a project by its path"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM projects WHERE path = ?', (path,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_all_projects(self, active_only: bool = True) -> List[Dict]:
        """Get all projects from database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if active_only:
            cursor.execute('SELECT * FROM projects WHERE status = "active" ORDER BY name')
        else:
            cursor.execute('SELECT * FROM projects ORDER BY name')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_dirty_projects(self) -> List[Dict]:
        """Get projects marked as dirty (need re-analysis)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM projects WHERE dirty_flag = 1 AND status = "active"')
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def upsert_project(self, project_data: Dict) -> int:
        """Insert or update a project"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if project exists
        cursor.execute('SELECT id FROM projects WHERE path = ?', (project_data['path'],))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing project
            project_data['updated_at'] = datetime.now().isoformat()
            
            update_fields = []
            update_values = []
            
            for key, value in project_data.items():
                if key != 'path':  # Don't update the path (it's the key)
                    update_fields.append(f"{key} = ?")
                    update_values.append(value)
            
            update_values.append(project_data['path'])
            
            query = f"UPDATE projects SET {', '.join(update_fields)} WHERE path = ?"
            cursor.execute(query, update_values)
            
            project_id = existing[0]
            logger.info(f"Updated project: {project_data.get('name', 'Unknown')}")
        else:
            # Insert new project
            project_data['created_at'] = datetime.now().isoformat()
            project_data['updated_at'] = datetime.now().isoformat()
            
            fields = list(project_data.keys())
            placeholders = ', '.join(['?' for _ in fields])
            query = f"INSERT INTO projects ({', '.join(fields)}) VALUES ({placeholders})"
            
            cursor.execute(query, list(project_data.values()))
            project_id = cursor.lastrowid
            logger.info(f"Added new project: {project_data.get('name', 'Unknown')}")
        
        conn.commit()
        conn.close()
        
        return project_id
    
    def mark_project_dirty(self, path: str):
        """Mark a project as dirty for re-analysis"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE projects SET dirty_flag = 1, updated_at = ? WHERE path = ?',
            (datetime.now().isoformat(), path)
        )
        
        conn.commit()
        conn.close()
        logger.info(f"Marked project as dirty: {path}")
    
    def mark_project_clean(self, path: str):
        """Mark a project as clean (analysis complete)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE projects SET dirty_flag = 0, last_scanned = ?, updated_at = ? WHERE path = ?',
            (datetime.now().isoformat(), datetime.now().isoformat(), path)
        )
        
        conn.commit()
        conn.close()
    
    def mark_project_inactive(self, path: str):
        """Mark a project as inactive (directory no longer exists)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE projects SET status = "inactive", updated_at = ? WHERE path = ?',
            (datetime.now().isoformat(), path)
        )
        
        conn.commit()
        conn.close()
        logger.warning(f"Marked project as inactive: {path}")
    
    def start_scan_session(self, session_id: str, directories: List[str]) -> int:
        """Start a new scan session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO scan_sessions (session_id, start_time, directories_scanned) VALUES (?, ?, ?)',
            (session_id, datetime.now().isoformat(), json.dumps(directories))
        )
        
        session_db_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Started scan session: {session_id}")
        return session_db_id
    
    def end_scan_session(self, session_id: str, projects_found: int, projects_updated: int):
        """End a scan session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE scan_sessions SET end_time = ?, projects_found = ?, projects_updated = ?, status = "completed" WHERE session_id = ?',
            (datetime.now().isoformat(), projects_found, projects_updated, session_id)
        )
        
        conn.commit()
        conn.close()
        logger.info(f"Completed scan session: {session_id} - Found: {projects_found}, Updated: {projects_updated}")
    
    def get_scan_history(self, limit: int = 10) -> List[Dict]:
        """Get recent scan sessions"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT * FROM scan_sessions ORDER BY start_time DESC LIMIT ?',
            (limit,)
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def cleanup_old_sessions(self, days: int = 30):
        """Clean up old scan sessions"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'DELETE FROM scan_sessions WHERE start_time < ?',
            (cutoff_date.isoformat(),)
        )
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old scan sessions")
    
    def toggle_favorite_status(self, path: str) -> bool:
        """Toggle favorite status of a project and return new status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current status
        cursor.execute('SELECT is_favorite FROM projects WHERE path = ?', (path,))
        result = cursor.fetchone()
        
        if result is None:
            conn.close()
            logger.warning(f"Project not found for favorite toggle: {path}")
            return False
        
        current_status = bool(result[0])
        new_status = not current_status
        
        # Update status
        cursor.execute(
            'UPDATE projects SET is_favorite = ?, updated_at = ? WHERE path = ?',
            (new_status, datetime.now().isoformat(), path)
        )
        
        conn.commit()
        conn.close()
        
        logger.info(f"Toggled favorite status for {path}: {current_status} -> {new_status}")
        return new_status
    
    def toggle_hidden_status(self, path: str) -> bool:
        """Toggle hidden status of a project and return new status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current status
        cursor.execute('SELECT is_hidden FROM projects WHERE path = ?', (path,))
        result = cursor.fetchone()
        
        if result is None:
            conn.close()
            logger.warning(f"Project not found for hidden toggle: {path}")
            return False
        
        current_status = bool(result[0])
        new_status = not current_status
        
        # Update status
        cursor.execute(
            'UPDATE projects SET is_hidden = ?, updated_at = ? WHERE path = ?',
            (new_status, datetime.now().isoformat(), path)
        )
        
        conn.commit()
        conn.close()
        
        logger.info(f"Toggled hidden status for {path}: {current_status} -> {new_status}")
        return new_status
    
    def get_favorite_projects(self) -> List[Dict]:
        """Get all favorite projects"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM projects WHERE status = "active" AND is_favorite = 1 ORDER BY name')
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_hidden_projects(self) -> List[Dict]:
        """Get all hidden projects"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM projects WHERE status = "active" AND is_hidden = 1 ORDER BY name')
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_visible_projects(self) -> List[Dict]:
        """Get all visible (non-hidden, non-favorite) projects"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM projects WHERE status = "active" AND is_hidden = 0 AND is_favorite = 0 ORDER BY name')
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Project counts
        cursor.execute('SELECT COUNT(*) FROM projects WHERE status = "active"')
        active_projects = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM projects WHERE dirty_flag = 1')
        dirty_projects = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM scan_sessions')
        total_sessions = cursor.fetchone()[0]
        
        # Last scan
        cursor.execute('SELECT MAX(start_time) FROM scan_sessions')
        last_scan = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'active_projects': active_projects,
            'dirty_projects': dirty_projects,
            'total_sessions': total_sessions,
            'last_scan': last_scan
        }

# Global database instance
db = ProjectDatabase() 