import gradio as gr
import sqlite3
import pandas as pd
from typing import List, Dict, Any, Tuple
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
        
        schema_text = f"## Schema for `{table_name}` table\n\n"
        schema_text += "| Column | Type | Not Null | Default | Primary Key |\n"
        schema_text += "|--------|------|----------|---------|-------------|\n"
        
        for col in schema:
            cid, name, col_type, not_null, default, pk = col
            schema_text += f"| {name} | {col_type} | {'Yes' if not_null else 'No'} | {default or 'NULL'} | {'Yes' if pk else 'No'} |\n"
        
        return schema_text
    
    def get_default_query(self, table_name: str = "projects") -> str:
        """Get a sensible default query for a table"""
        if table_name == "projects":
            return f"""SELECT 
    id,
    name,
    path,
    launch_command
FROM {table_name} 
ORDER BY id ASC 
LIMIT 100"""
        else:
            return f"SELECT * FROM {table_name} LIMIT 50"
    
    def execute_query(self, query: str) -> Tuple[pd.DataFrame, str]:
        """Execute a SQL query and return results"""
        try:
            conn = sqlite3.connect(self.db.db_path)
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            # Truncate very long text fields for display
            for col in df.columns:
                if df[col].dtype == 'object':  # String columns
                    # Truncate very long strings
                    df[col] = df[col].astype(str).apply(lambda x: x[:100] + "..." if len(str(x)) > 100 else x)
            
            message = f"✅ Query executed successfully. Returned {len(df)} rows."
            return df, message
        except Exception as e:
            return pd.DataFrame(), f"❌ Error: {str(e)}"
    
    def get_database_stats(self) -> str:
        """Get comprehensive database statistics"""
        try:
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
- **Projects Updated Today:** {today_updates}
- **New Projects Today:** {today_new}

## Environment Breakdown
"""
            for env_type, count in env_stats:
                stats_text += f"- **{env_type or 'Unknown'}:** {count} projects\n"
            
            return stats_text
        except Exception as e:
            return f"❌ Error getting stats: {str(e)}"

def build_database_ui():
    """Build the database UI components"""
    db_ui = DatabaseUI()
    
    with gr.Column():
        gr.Markdown("## 🗄️ Database Explorer")
        gr.Markdown("Direct SQL access to the project database with live query editing")
        
        # Sub-tabs within the database
        with gr.Tabs():
            # Query Tab
            with gr.Tab("🔍 Query"):
                with gr.Column():
                    # SQL Query Interface
                    gr.Markdown("### SQL Query Editor")
                    with gr.Row():
                        with gr.Column():
                            sql_query = gr.Textbox(
                                label="SQL Query",
                                value=db_ui.get_default_query("projects"),
                                lines=8,
                                placeholder="Enter your SQL query here...",
                                interactive=True
                            )
                            
                            with gr.Row():
                                execute_btn = gr.Button("▶️ Execute Query", variant="primary")
                                load_default_btn = gr.Button("📝 Load Default Query")
                                clear_btn = gr.Button("🗑️ Clear")
                    
                    # Query status
                    query_status = gr.Markdown("Ready to execute query")
                    
                    # Results display
                    gr.Markdown("### 📊 Query Results")
                    with gr.Row():
                        results_table = gr.Dataframe(
                            label="Results",
                            interactive=False,
                            wrap=True,
                            column_widths=["10%", "20%", "30%", "15%", "15%", "10%"]  # Default widths
                        )
                    
                    gr.Markdown("""
### 💡 Usage Tips
- **Column Widths**: Adjust the `column_widths` parameter in code for custom column sizing
- **Large Data**: The `icon_data` column contains base64 images - uncomment carefully!
- **Performance**: Use `LIMIT` clauses for large tables
- **Safety**: Only SELECT queries are recommended for data integrity
                    """)
            
            # Schema Tab
            with gr.Tab("📋 Schema"):
                with gr.Column():
                    gr.Markdown("### Tables & Schema Information")
                    
                    # Table selector
                    with gr.Row():
                        table_dropdown = gr.Dropdown(
                            choices=db_ui.get_table_list(),
                            value="projects" if "projects" in db_ui.get_table_list() else None,
                            label="Select Table",
                            interactive=True
                        )
                    
                    # Schema display
                    schema_display = gr.Markdown(
                        db_ui.get_table_schema("projects") if "projects" in db_ui.get_table_list() else "Select a table to view schema"
                    )
                    
                    # Additional table info
                    gr.Markdown("""
### 📖 Schema Information
- **Primary Key**: Unique identifier for each row
- **Not Null**: Whether the column requires a value
- **Default**: Default value when no value is provided
- **Type**: Data type of the column (TEXT, INTEGER, REAL, BOOLEAN, TIMESTAMP)
                    """)
            
            # Statistics Tab
            with gr.Tab("📊 Statistics"):
                with gr.Column():
                    gr.Markdown("### Database Statistics")
                    
                    # Database statistics
                    with gr.Row():
                        with gr.Column(scale=4):
                            stats_display = gr.Markdown(db_ui.get_database_stats())
                        with gr.Column(scale=1):
                            refresh_stats_btn = gr.Button("🔄 Refresh Stats", variant="secondary")
                    
                    # Additional stats info
                    gr.Markdown("""
### 📈 Statistics Information
- **Database Size**: Physical size of the SQLite database file
- **Active Projects**: Projects with status = 'active'
- **Projects Needing Analysis**: Projects with dirty_flag = True
- **Environment Breakdown**: Count of projects by detected environment type
- **Activity**: Recent project updates and additions
                    """)
        
        # Event handlers
        def update_schema(table_name):
            """Update schema display when table is selected"""
            if table_name:
                return db_ui.get_table_schema(table_name)
            return "Select a table to view schema"
        
        def load_default_query(table_name="projects"):
            """Load default query for selected table"""
            return db_ui.get_default_query(table_name)
        
        def execute_user_query(query):
            """Execute the user's SQL query"""
            df, status = db_ui.execute_query(query)
            return df, status
        
        def refresh_stats():
            """Refresh database statistics"""
            return db_ui.get_database_stats()
        
        def clear_query():
            """Clear the query textbox"""
            return ""
        
        # Wire up events
        table_dropdown.change(
            update_schema,
            inputs=[table_dropdown],
            outputs=[schema_display]
        )
        
        load_default_btn.click(
            load_default_query,
            outputs=[sql_query]
        )
        
        execute_btn.click(
            execute_user_query,
            inputs=[sql_query],
            outputs=[results_table, query_status]
        )
        
        refresh_stats_btn.click(
            refresh_stats,
            outputs=[stats_display]
        )
        
        clear_btn.click(
            clear_query,
            outputs=[sql_query]
        ) 