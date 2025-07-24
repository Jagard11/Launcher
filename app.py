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
    
    # Create the main interface with tabs
    with gr.Blocks(title="AI Launcher", theme=gr.themes.Soft()) as app:
        gr.Markdown("# AI Project Launcher")
        gr.Markdown("Discover and launch your AI projects with automatic environment detection")
        
        with gr.Tabs() as tabs:
            # App List tab (default)
            with gr.Tab("App List", id="app_list") as app_list_tab:
                build_launcher_ui(config)
            
            # Database tab
            with gr.Tab("Database", id="database") as database_tab:
                build_database_ui()
        
        # Add JavaScript for comprehensive URL management including subtabs
        app.load(
            fn=None,
            inputs=[],
            outputs=[],
            js="""
            function() {
                // Function to update URL with current tab and subtab
                function updateURL(tabName, subtabName = null) {
                    const url = new URL(window.location);
                    url.searchParams.set('tab', tabName);
                    
                    if (subtabName) {
                        url.searchParams.set('subtab', subtabName);
                    } else {
                        url.searchParams.delete('subtab');
                    }
                    
                    window.history.pushState({tab: tabName, subtab: subtabName}, '', url);
                }
                
                // Function to get tab name from button text
                function getTabName(buttonText) {
                    return buttonText.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
                }
                
                // Function to find and activate tab from URL
                function activateTabFromURL() {
                    const urlParams = new URLSearchParams(window.location.search);
                    const requestedTab = urlParams.get('tab');
                    const requestedSubtab = urlParams.get('subtab');
                    
                    if (requestedTab) {
                        // Find and activate main tab
                        const mainTabButtons = document.querySelectorAll('div[role="tablist"] > button[role="tab"]');
                        mainTabButtons.forEach(button => {
                            const tabName = getTabName(button.textContent);
                            if (tabName === requestedTab) {
                                button.click();
                                
                                // If there's a subtab parameter, handle it after main tab is activated
                                if (requestedSubtab && requestedTab === 'database') {
                                    setTimeout(() => activateSubtabFromURL(requestedSubtab), 300);
                                }
                            }
                        });
                    }
                }
                
                // Function to activate subtab from URL (specifically for database tab)
                function activateSubtabFromURL(requestedSubtab) {
                    // Find all tab containers and look for the database subtabs
                    const allTabContainers = document.querySelectorAll('div[role="tablist"]');
                    
                    allTabContainers.forEach(container => {
                        // Skip main tab container
                        const isMainTabContainer = Array.from(container.children).some(child => 
                            child.textContent.includes('App List') || child.textContent.includes('Database')
                        );
                        
                        if (!isMainTabContainer) {
                            const subtabButtons = container.querySelectorAll('button[role="tab"]');
                            subtabButtons.forEach(button => {
                                const subtabName = getTabName(button.textContent);
                                if (subtabName === requestedSubtab) {
                                    button.click();
                                }
                            });
                        }
                    });
                }
                
                // Function to set up tab change listeners for main tabs
                function setupMainTabListeners() {
                    const mainTabButtons = document.querySelectorAll('div[role="tablist"] > button[role="tab"]');
                    
                    // Use MutationObserver to detect main tab changes
                    const observer = new MutationObserver((mutations) => {
                        mutations.forEach((mutation) => {
                            if (mutation.type === 'attributes' && 
                                mutation.attributeName === 'aria-selected' && 
                                mutation.target.getAttribute('aria-selected') === 'true') {
                                
                                const tabName = getTabName(mutation.target.textContent);
                                
                                // Check if this is a main tab (not a subtab)
                                const isMainTab = Array.from(mainTabButtons).includes(mutation.target);
                                
                                if (isMainTab) {
                                    // Clear subtab parameter when switching main tabs
                                    updateURL(tabName);
                                    
                                    // Set up subtab listeners if we're on database tab
                                    if (tabName === 'database') {
                                        setTimeout(setupSubtabListeners, 500);
                                    }
                                }
                            }
                        });
                    });
                    
                    // Observe each main tab button
                    mainTabButtons.forEach(button => {
                        observer.observe(button, { 
                            attributes: true, 
                            attributeFilter: ['aria-selected'] 
                        });
                    });
                }
                
                // Function to set up subtab listeners (for database tab)
                function setupSubtabListeners() {
                    const allTabContainers = document.querySelectorAll('div[role="tablist"]');
                    
                    allTabContainers.forEach(container => {
                        // Skip main tab container
                        const isMainTabContainer = Array.from(container.children).some(child => 
                            child.textContent.includes('App List') || child.textContent.includes('Database')
                        );
                        
                        if (!isMainTabContainer) {
                            const subtabButtons = container.querySelectorAll('button[role="tab"]');
                            
                            if (subtabButtons.length > 0) {
                                // Use MutationObserver for subtabs
                                const subtabObserver = new MutationObserver((mutations) => {
                                    mutations.forEach((mutation) => {
                                        if (mutation.type === 'attributes' && 
                                            mutation.attributeName === 'aria-selected' && 
                                            mutation.target.getAttribute('aria-selected') === 'true') {
                                            
                                            const subtabName = getTabName(mutation.target.textContent);
                                            const currentTab = new URLSearchParams(window.location.search).get('tab') || 'database';
                                            updateURL(currentTab, subtabName);
                                        }
                                    });
                                });
                                
                                // Observe each subtab button
                                subtabButtons.forEach(button => {
                                    subtabObserver.observe(button, { 
                                        attributes: true, 
                                        attributeFilter: ['aria-selected'] 
                                    });
                                });
                            }
                        }
                    });
                }
                
                // Handle browser back/forward buttons
                window.addEventListener('popstate', (event) => {
                    if (event.state && event.state.tab) {
                        activateTabFromURL();
                    } else {
                        // Fallback to reading URL directly
                        activateTabFromURL();
                    }
                });
                
                // Initialize after DOM is ready
                function initialize() {
                    setupMainTabListeners();
                    activateTabFromURL();
                    
                    // Check if we're on database tab and set up subtab listeners
                    const urlParams = new URLSearchParams(window.location.search);
                    const currentTab = urlParams.get('tab');
                    if (currentTab === 'database') {
                        setTimeout(setupSubtabListeners, 1000);
                    }
                }
                
                // Multiple initialization attempts to handle dynamic content
                setTimeout(initialize, 500);
                
                const initInterval = setInterval(() => {
                    const mainTabButtons = document.querySelectorAll('div[role="tablist"] > button[role="tab"]');
                    if (mainTabButtons.length > 0) {
                        clearInterval(initInterval);
                        initialize();
                    }
                }, 100);
                
                // Clear interval after 10 seconds to prevent infinite checking
                setTimeout(() => clearInterval(initInterval), 10000);
                
                return [];
            }
            """
        )
    
    return app

if __name__ == "__main__":
    app = main()
    app.launch(share=False, server_name="0.0.0.0", server_port=7860) 