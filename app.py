import gradio as gr
import json
from pathlib import Path
from launcher_ui import build_launcher_ui
from database_ui import build_database_ui

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

def main():
    """Main application entry point"""
    config = load_config()
    
    # Create the main interface with custom tab buttons
    with gr.Blocks(title="AI Launcher", theme=gr.themes.Soft()) as app:
        # State management for tabs
        current_main_tab = gr.State(value="app_list")
        current_subtab = gr.State(value="query")
        
        gr.Markdown("# AI Project Launcher")
        gr.Markdown("Discover and launch your AI projects with automatic environment detection")
        
        # Main tab buttons
        with gr.Row():
            app_list_btn = gr.Button("App List", variant="primary", size="lg")
            database_btn = gr.Button("Database", variant="secondary", size="lg")
        
        # Content areas
        with gr.Column(visible=True) as app_list_content:
                build_launcher_ui(config)
        
        with gr.Column(visible=False) as database_content:
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
                # SQL Query Interface
                gr.Markdown("### SQL Query Editor")
                with gr.Row():
                    with gr.Column():
                        sql_query = gr.Textbox(
                            label="SQL Query",
                            value="SELECT id, name, path, launch_command FROM projects ORDER BY id ASC LIMIT 100",
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
                results_table = gr.Dataframe(
                    label="Results",
                    interactive=False,
                    wrap=True
                )
                
                gr.Markdown("""
### 💡 Usage Tips
- **Performance**: Use `LIMIT` clauses for large tables
- **Safety**: Only SELECT queries are recommended for data integrity
                """)
            
            with gr.Column(visible=False) as schema_content:
                gr.Markdown("### Tables & Schema Information")
                
                # Table selector
                with gr.Row():
                    table_dropdown = gr.Dropdown(
                        choices=["projects", "scan_sessions"],
                        value="projects",
                        label="Select Table",
                        interactive=True
                    )
                
                # Schema display
                schema_display = gr.Markdown("## Schema for `projects` table\n\nSelect a table to view schema information.")
            
            with gr.Column(visible=False) as stats_content:
                gr.Markdown("### Database Statistics")
                
                with gr.Row():
                    with gr.Column(scale=4):
                        stats_display = gr.Markdown("Loading statistics...")
                    with gr.Column(scale=1):
                        refresh_stats_btn = gr.Button("🔄 Refresh Stats", variant="secondary")
            
            with gr.Column(visible=False) as tools_content:
                gr.Markdown("### Project Management Tools")
                gr.Markdown("Advanced tools for managing project launch methods and database maintenance")
                
                # Launch Command Rebuilding
                gr.Markdown("### 🔄 Launch Command Management")
                
                with gr.Row():
                    with gr.Column(scale=2):
                        rebuild_launch_btn = gr.Button("🔄 Rebuild All Launch Commands", variant="primary")
                    with gr.Column(scale=3):
                        gr.Markdown("**Rebuild All Launch Commands**: Re-analyzes all projects using the new AI detection system.")
                
                # Tools output
                tools_output = gr.Textbox(
                    label="Tools Output", 
                    interactive=False, 
                    lines=8,
                    placeholder="Tool execution results will appear here..."
                )
        
        # Tab switching functions
        def switch_to_app_list():
            return (
                "app_list",  # current_main_tab
                "",  # current_subtab  
                gr.update(variant="primary"),  # app_list_btn
                gr.update(variant="secondary"),  # database_btn
                gr.update(visible=True),  # app_list_content
                gr.update(visible=False),  # database_content
            )
        
        def switch_to_database():
            return (
                "database",  # current_main_tab
                "query",  # current_subtab
                gr.update(variant="secondary"),  # app_list_btn
                gr.update(variant="primary"),  # database_btn
                gr.update(visible=False),  # app_list_content
                gr.update(visible=True),  # database_content
            )
        
        def switch_to_query():
            return (
                "query",  # current_subtab
                gr.update(variant="primary"),  # query_btn
                gr.update(variant="secondary"),  # schema_btn
                gr.update(variant="secondary"),  # stats_btn
                gr.update(variant="secondary"),  # tools_btn
                gr.update(visible=True),  # query_content
                gr.update(visible=False),  # schema_content
                gr.update(visible=False),  # stats_content
                gr.update(visible=False),  # tools_content
            )
        
        def switch_to_schema():
            return (
                "schema",  # current_subtab
                gr.update(variant="secondary"),  # query_btn
                gr.update(variant="primary"),  # schema_btn
                gr.update(variant="secondary"),  # stats_btn
                gr.update(variant="secondary"),  # tools_btn
                gr.update(visible=False),  # query_content
                gr.update(visible=True),  # schema_content
                gr.update(visible=False),  # stats_content
                gr.update(visible=False),  # tools_content
            )
        
        def switch_to_stats():
            return (
                "statistics",  # current_subtab
                gr.update(variant="secondary"),  # query_btn
                gr.update(variant="secondary"),  # schema_btn
                gr.update(variant="primary"),  # stats_btn
                gr.update(variant="secondary"),  # tools_btn
                gr.update(visible=False),  # query_content
                gr.update(visible=False),  # schema_content
                gr.update(visible=True),  # stats_content
                gr.update(visible=False),  # tools_content
            )
        
        def switch_to_tools():
            return (
                "tools",  # current_subtab
                gr.update(variant="secondary"),  # query_btn
                gr.update(variant="secondary"),  # schema_btn
                gr.update(variant="secondary"),  # stats_btn
                gr.update(variant="primary"),  # tools_btn
                gr.update(visible=False),  # query_content
                gr.update(visible=False),  # schema_content
                gr.update(visible=False),  # stats_content
                gr.update(visible=True),  # tools_content
            )
        
        # Wire up main tab buttons
        app_list_btn.click(
            fn=switch_to_app_list,
            outputs=[
                current_main_tab, current_subtab,
                app_list_btn, database_btn,
                app_list_content, database_content
            ]
        )
        
        database_btn.click(
            fn=switch_to_database,
            outputs=[
                current_main_tab, current_subtab,
                app_list_btn, database_btn,
                app_list_content, database_content
            ]
        )
        
        # Wire up subtab buttons
        query_btn.click(
            fn=switch_to_query,
            outputs=[
                current_subtab,
                query_btn, schema_btn, stats_btn, tools_btn,
                query_content, schema_content, stats_content, tools_content
            ]
        )
        
        schema_btn.click(
            fn=switch_to_schema,
            outputs=[
                current_subtab,
                query_btn, schema_btn, stats_btn, tools_btn,
                query_content, schema_content, stats_content, tools_content
            ]
        )
        
        stats_btn.click(
            fn=switch_to_stats,
            outputs=[
                current_subtab,
                query_btn, schema_btn, stats_btn, tools_btn,
                query_content, schema_content, stats_content, tools_content
            ]
        )
        
        tools_btn.click(
            fn=switch_to_tools,
            outputs=[
                current_subtab,
                query_btn, schema_btn, stats_btn, tools_btn,
                query_content, schema_content, stats_content, tools_content
            ]
        )
        
        # JavaScript for URL management
        app.load(
            fn=None,
            inputs=[],
            outputs=[],
            js="""
            function() {
                console.log('🚀 Custom Tab Router: Initializing...');
                
                // Function to update URL
                function updateURL(tab, subtab = '') {
                    const url = new URL(window.location);
                    url.searchParams.set('tab', tab);
                    
                    if (subtab && subtab !== '') {
                        url.searchParams.set('subtab', subtab);
                    } else {
                        url.searchParams.delete('subtab');
                    }
                    
                    window.history.pushState({tab: tab, subtab: subtab}, '', url);
                    console.log('🔗 URL updated:', url.href);
                }
                
                // Function to activate tab from URL on page load
                function activateTabFromURL() {
                    const urlParams = new URLSearchParams(window.location.search);
                    const requestedTab = urlParams.get('tab') || 'app_list';
                    const requestedSubtab = urlParams.get('subtab') || 'query';
                    
                    console.log(`📍 Activating from URL: tab=${requestedTab}, subtab=${requestedSubtab}`);
                    
                    // Find and click the appropriate main tab button
                    setTimeout(() => {
                        const buttons = document.querySelectorAll('button');
                        
                        for (const button of buttons) {
                            const buttonText = button.textContent.toLowerCase().trim();
                            
                            if ((requestedTab === 'app_list' && buttonText === 'app list') ||
                                (requestedTab === 'database' && buttonText === 'database')) {
                                console.log(`🎯 Clicking main tab: ${button.textContent}`);
                                button.click();
                                
                                // If database tab, also click subtab
                                if (requestedTab === 'database') {
                                    setTimeout(() => {
                                        activateSubtab(requestedSubtab);
                                    }, 300);
                                }
                                break;
                            }
                        }
                    }, 500);
                }
                
                // Function to activate subtab
                function activateSubtab(requestedSubtab) {
                    console.log(`🎯 Looking for subtab: ${requestedSubtab}`);
                    
                    const buttons = document.querySelectorAll('button');
                    
                    for (const button of buttons) {
                        const buttonText = button.textContent.toLowerCase().replace(/[🔍📋📊🛠️]/g, '').trim();
                        
                        if ((requestedSubtab === 'query' && buttonText === 'query') ||
                            (requestedSubtab === 'schema' && buttonText === 'schema') ||
                            (requestedSubtab === 'statistics' && buttonText === 'statistics') ||
                            (requestedSubtab === 'tools' && buttonText === 'tools')) {
                            console.log(`🎯 Clicking subtab: ${button.textContent}`);
                            button.click();
                            break;
                        }
                    }
                }
                
                // Monitor button clicks to update URL
                function setupButtonMonitoring() {
                    const observer = new MutationObserver((mutations) => {
                        mutations.forEach((mutation) => {
                            if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                                const button = mutation.target;
                                
                                if (button.tagName === 'BUTTON' && button.classList.contains('primary')) {
                                    const buttonText = button.textContent.toLowerCase().trim();
                                    console.log(`👆 Button activated: ${button.textContent}`);
                                    
                                    // Main tab buttons
                                    if (buttonText === 'app list') {
                                        updateURL('app_list');
                                    } else if (buttonText === 'database') {
                                        updateURL('database', 'query');
                                    }
                                    // Subtab buttons
                                    else if (buttonText.includes('query')) {
                                        updateURL('database', 'query');
                                    } else if (buttonText.includes('schema')) {
                                        updateURL('database', 'schema');
                                    } else if (buttonText.includes('statistics')) {
                                        updateURL('database', 'statistics');
                                    } else if (buttonText.includes('tools')) {
                                        updateURL('database', 'tools');
                                    }
                                }
                            }
                        });
                    });
                    
                    observer.observe(document.body, {
                        attributes: true,
                        subtree: true,
                        attributeFilter: ['class']
                    });
                    
                    console.log('📊 Button monitoring active');
                }
                
                // Handle browser back/forward
                window.addEventListener('popstate', (event) => {
                    console.log('⬅️ Browser navigation detected');
                    activateTabFromURL();
                });
                
                // Initialize
                setTimeout(() => {
                    setupButtonMonitoring();
                    activateTabFromURL();
                }, 1000);
                
                return [];
            }
            """
        )
    
    return app

if __name__ == "__main__":
    app = main()
    app.launch(share=False, server_name="0.0.0.0", server_port=7860) 