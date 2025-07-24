import gradio as gr
import sqlite3
import pandas as pd
from typing import List, Dict, Any
from project_database import db
import json
from datetime import datetime

class DatabaseUI:
    def __init__(self):
        self.db = db
        
    def get_table_list(self) -> List[str]:
        """Get list of all tables in the database"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables
    
    def get_table_schema(self, table_name: str) -> str:
        """Get the schema for a specific table"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        schema = cursor.fetchall()
        conn.close()
        
        schema_text = f"### Table: {table_name}\n\n"
        schema_text += "| Column | Type | Not Null | Default | Primary Key |\n"
        schema_text += "|--------|------|----------|---------|-------------|\n"
        
        for col in schema:
            cid, name, col_type, not_null, default, pk = col
            schema_text += f"| {name} | {col_type} | {'Yes' if not_null else 'No'} | {default or 'NULL'} | {'Yes' if pk else 'No'} |\n"
        
        return schema_text
    
    def get_table_data(self, table_name: str, limit: int = 100) -> pd.DataFrame:
        """Get data from a specific table"""
        conn = sqlite3.connect(self.db.db_path)
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    
    def execute_custom_query(self, query: str) -> tuple[pd.DataFrame, str]:
        """Execute a custom SQL query"""
        try:
            conn = sqlite3.connect(self.db.db_path)
            df = pd.read_sql_query(query, conn)
            conn.close()
            return df, "✅ Query executed successfully"
        except Exception as e:
            return pd.DataFrame(), f"❌ Error: {str(e)}"
    
    def get_database_stats(self) -> str:
        """Get comprehensive database statistics"""
        stats = self.db.get_stats()
        
        # Get additional stats
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        # Database file size
        import os
        db_size = os.path.getsize(self.db.db_path) / 1024 / 1024  # MB
        
        # Project environment breakdown
        cursor.execute("SELECT environment_type, COUNT(*) as count FROM projects WHERE status = 'active' GROUP BY environment_type")
        env_stats = cursor.fetchall()
        
        # Recent activity
        cursor.execute("SELECT COUNT(*) FROM projects WHERE date(updated_at) = date('now')")
        today_updates = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM projects WHERE date(created_at) = date('now')")
        today_new = cursor.fetchone()[0]
        
        conn.close()
        
        stats_text = f"""# Database Statistics
        
## Overview
- **Database Size:** {db_size:.2f} MB
- **Active Projects:** {stats['active_projects']}
- **Projects Needing Analysis:** {stats['dirty_projects']}
- **Total Scan Sessions:** {stats['total_sessions']}
- **Last Scan:** {stats['last_scan'] or 'Never'}

## Today's Activity
- **Projects Updated:** {today_updates}
- **New Projects Added:** {today_new}

## Environment Breakdown
"""
        
        for env_type, count in env_stats:
            stats_text += f"- **{env_type or 'Unknown'}:** {count} projects\n"
        
        return stats_text

def build_database_ui():
    """Build the database UI components"""
    db_ui = DatabaseUI()
    
    with gr.Column():
        gr.Markdown("## Database Overview")
        
        # Database statistics
        stats_display = gr.Markdown(db_ui.get_database_stats())
        refresh_stats_btn = gr.Button("🔄 Refresh Stats", size="sm")
        
        gr.Markdown("---")
        
        # Table browser
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Tables")
                table_dropdown = gr.Dropdown(
                    choices=db_ui.get_table_list(),
                    value="projects" if "projects" in db_ui.get_table_list() else None,
                    label="Select Table",
                    interactive=True
                )
                
                limit_slider = gr.Slider(
                    minimum=10,
                    maximum=1000,
                    value=100,
                    step=10,
                    label="Row Limit"
                )
                
                load_table_btn = gr.Button("📊 Load Table Data", variant="primary")
            
            with gr.Column(scale=2):
                gr.Markdown("### Table Schema")
                schema_display = gr.Markdown("")
        
        # Table data display
        gr.Markdown("### Table Data")
        table_data = gr.Dataframe(
            label="Table Contents",
            interactive=False,
            wrap=True
        )
        
        gr.Markdown("---")
        
        # Custom query section
        gr.Markdown("### Custom SQL Query")
        with gr.Row():
            query_input = gr.Textbox(
                label="SQL Query",
                placeholder="SELECT * FROM projects WHERE environment_type = 'conda' LIMIT 10",
                lines=3
            )
        
        with gr.Row():
            execute_btn = gr.Button("▶️ Execute Query", variant="secondary")
            query_status = gr.Textbox(label="Status", interactive=False, scale=2)
        
        query_results = gr.Dataframe(
            label="Query Results",
            interactive=False,
            wrap=True
        )
        
        # Event handlers
        def update_schema(table_name):
            if table_name:
                return db_ui.get_table_schema(table_name)
            return ""
        
        def load_table(table_name, limit):
            if table_name:
                df = db_ui.get_table_data(table_name, limit)
                return df
            return pd.DataFrame()
        
        def execute_query(query):
            if query.strip():
                df, status = db_ui.execute_custom_query(query)
                return df, status
            return pd.DataFrame(), "❌ Please enter a query"
        
        def refresh_stats():
            return db_ui.get_database_stats()
        
        # Wire up events
        table_dropdown.change(
            update_schema,
            inputs=[table_dropdown],
            outputs=[schema_display]
        )
        
        load_table_btn.click(
            load_table,
            inputs=[table_dropdown, limit_slider],
            outputs=[table_data]
        )
        
        execute_btn.click(
            execute_query,
            inputs=[query_input],
            outputs=[query_results, query_status]
        )
        
        refresh_stats_btn.click(
            refresh_stats,
            outputs=[stats_display]
        )
        
        # Load initial data
        if db_ui.get_table_list():
            table_dropdown.change(
                update_schema,
                inputs=[table_dropdown],
                outputs=[schema_display]
            ) 