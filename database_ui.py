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

def build_database_ui(launcher=None):
    """Build the database UI components"""
    db_ui = DatabaseUI()
    
    with gr.Column():
        gr.Markdown("## 🗄️ Database Explorer")
        gr.Markdown("Direct SQL access to the project database with live query editing")
        
        # Database subtab buttons
        with gr.Row():
            query_btn = gr.Button("🔍 Query", variant="primary", size="sm")
            schema_btn = gr.Button("📋 Schema", variant="secondary", size="sm")
            stats_btn = gr.Button("📊 Statistics", variant="secondary", size="sm")
            tools_btn = gr.Button("🛠️ Tools", variant="secondary", size="sm")
        
        # Database subtab content areas
        with gr.Column(visible=True) as query_content:
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
        
        with gr.Column(visible=False) as schema_content:
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
        
        with gr.Column(visible=False) as stats_content:
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
        
        with gr.Column(visible=False) as tools_content:
            with gr.Column():
                gr.Markdown("### Project Management Tools")
                gr.Markdown("Advanced tools for managing project launch methods and database maintenance")
                
                if launcher is not None:
                    # Launch Command Rebuilding
                    with gr.Row():
                        gr.Markdown("### 🔄 Launch Command Management")
                    
                    with gr.Row():
                        with gr.Column(scale=2):
                            rebuild_launch_btn = gr.Button(
                                "🔄 Rebuild All Launch Commands", 
                                variant="primary"
                            )
                        with gr.Column(scale=3):
                            gr.Markdown("""
**Rebuild All Launch Commands**: Re-analyzes all projects using the new AI detection system. 
This will mark all projects as dirty and trigger background processing to update launch methods.
                            """)
                    
                    # Individual Project Re-analysis
                    with gr.Row():
                        gr.Markdown("### 🔍 Individual Project Re-analysis")
                    
                    with gr.Row():
                        with gr.Column(scale=3):
                            reanalyze_path_input = gr.Textbox(
                                label="Project Path",
                                placeholder="Enter full project path to re-analyze launch method",
                                elem_id="tools_reanalyze_path_input"
                            )
                        with gr.Column(scale=1):
                            reanalyze_btn = gr.Button("🔍 Re-analyze Project", variant="secondary")
                    
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("""
**Individual Re-analysis**: Force immediate re-analysis of a specific project's launch method. 
Enter the full path to the project directory and click Re-analyze to update just that project.
                            """)
                    
                    # Database Maintenance
                    with gr.Row():
                        gr.Markdown("### 🧹 Database Maintenance")
                    
                    with gr.Row():
                        cleanup_btn = gr.Button("🧹 Cleanup Old Data", variant="secondary")
                        mark_all_dirty_btn = gr.Button("🏃 Mark All Dirty", variant="secondary")
                    
                    # Tools output
                    with gr.Row():
                        tools_output = gr.Textbox(
                            label="Tools Output", 
                            interactive=False, 
                            lines=8,
                            placeholder="Tool execution results will appear here..."
                        )
                    
                    # Helper functions
                    def mark_all_projects_dirty():
                        """Mark all projects as dirty for re-analysis"""
                        try:
                            from project_database import db
                            conn = sqlite3.connect(db.db_path)
                            cursor = conn.cursor()
                            cursor.execute("UPDATE projects SET dirty_flag = 1")
                            updated_count = cursor.rowcount
                            conn.commit()
                            conn.close()
                            
                            # Trigger background processing
                            if hasattr(launcher, 'scanner') and launcher.scanner:
                                launcher.scanner.trigger_dirty_cleanup()
                            
                            return f"✅ Marked {updated_count} projects as dirty for re-analysis. Background processing triggered."
                        except Exception as e:
                            return f"❌ Error marking projects as dirty: {str(e)}"
                    
                    def cleanup_database():
                        """Clean up old scan sessions and optimize database"""
                        try:
                            from project_database import db
                            
                            # Clean up old scan sessions (older than 30 days)
                            db.cleanup_old_sessions(days=30)
                            
                            # Optimize database
                            conn = sqlite3.connect(db.db_path)
                            cursor = conn.cursor()
                            cursor.execute("VACUUM")
                            conn.commit()
                            conn.close()
                            
                            return "✅ Database cleanup completed. Removed old scan sessions and optimized database."
                        except Exception as e:
                            return f"❌ Error during database cleanup: {str(e)}"
                    
                    # Wire up tool events
                    rebuild_launch_btn.click(
                        launcher.rebuild_launch_commands,
                        outputs=[tools_output]
                    )
                    
                    reanalyze_btn.click(
                        launcher.force_reanalyze_project,
                        inputs=[reanalyze_path_input],
                        outputs=[tools_output]
                    )
                    
                    mark_all_dirty_btn.click(
                        mark_all_projects_dirty,
                        outputs=[tools_output]
                    )
                    
                    cleanup_btn.click(
                        cleanup_database,
                        outputs=[tools_output]
                    )
                    
                else:
                    # Show message when launcher is not available
                    gr.Markdown("""
### ⚠️ Tools Unavailable

The project management tools are not available in this interface. 
Tools are only available when using the unified launcher.

**Available Tools (when launcher is available):**
- 🔄 Rebuild All Launch Commands
- 🔍 Individual Project Re-analysis  
- 🧹 Database Cleanup
- 🏃 Mark All Projects Dirty

**To access tools:** Use the unified launcher instead of the standalone database viewer.
                    """)
        
        # Subtab switching functions
        def switch_to_query():
            return (
                gr.update(variant="primary"),   # query_btn
                gr.update(variant="secondary"), # schema_btn
                gr.update(variant="secondary"), # stats_btn
                gr.update(variant="secondary"), # tools_btn
                gr.update(visible=True),        # query_content
                gr.update(visible=False),       # schema_content
                gr.update(visible=False),       # stats_content
                gr.update(visible=False),       # tools_content
            )
        
        def switch_to_schema():
            return (
                gr.update(variant="secondary"), # query_btn
                gr.update(variant="primary"),   # schema_btn
                gr.update(variant="secondary"), # stats_btn
                gr.update(variant="secondary"), # tools_btn
                gr.update(visible=False),       # query_content
                gr.update(visible=True),        # schema_content
                gr.update(visible=False),       # stats_content
                gr.update(visible=False),       # tools_content
            )
        
        def switch_to_stats():
            return (
                gr.update(variant="secondary"), # query_btn
                gr.update(variant="secondary"), # schema_btn
                gr.update(variant="primary"),   # stats_btn
                gr.update(variant="secondary"), # tools_btn
                gr.update(visible=False),       # query_content
                gr.update(visible=False),       # schema_content
                gr.update(visible=True),        # stats_content
                gr.update(visible=False),       # tools_content
            )
        
        def switch_to_tools():
            return (
                gr.update(variant="secondary"), # query_btn
                gr.update(variant="secondary"), # schema_btn
                gr.update(variant="secondary"), # stats_btn
                gr.update(variant="primary"),   # tools_btn
                gr.update(visible=False),       # query_content
                gr.update(visible=False),       # schema_content
                gr.update(visible=False),       # stats_content
                gr.update(visible=True),        # tools_content
            )
        
        # Wire up subtab buttons
        query_btn.click(
            fn=switch_to_query,
            outputs=[
                query_btn, schema_btn, stats_btn, tools_btn,
                query_content, schema_content, stats_content, tools_content
            ]
        )
        
        schema_btn.click(
            fn=switch_to_schema,
            outputs=[
                query_btn, schema_btn, stats_btn, tools_btn,
                query_content, schema_content, stats_content, tools_content
            ]
        )
        
        stats_btn.click(
            fn=switch_to_stats,
            outputs=[
                query_btn, schema_btn, stats_btn, tools_btn,
                query_content, schema_content, stats_content, tools_content
            ]
        )
        
        tools_btn.click(
            fn=switch_to_tools,
            outputs=[
                query_btn, schema_btn, stats_btn, tools_btn,
                query_content, schema_content, stats_content, tools_content
            ]
        )
        
        # Event handlers for non-tools tabs
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
        
        # Wire up events for non-tools tabs
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