# 🚀 AI Project Launcher

A sophisticated Gradio-based application that automatically discovers, categorizes, and launches AI/ML projects with **intelligent AI-powered launch command generation**. Features comprehensive project analysis using Qwen models, automatic environment detection, persistent caching, background scanning, and one-click project launching.

## ✨ Key Features

- **🧠 AI-Powered Launch Commands**: Uses Qwen models to intelligently analyze projects and generate optimal launch commands
- **🔍 Automatic Project Discovery**: Scans specified directories for AI/ML projects with smart detection
- **🐍 Environment Detection**: Automatically detects Python environments (conda, venv, poetry, pipenv)
- **🤖 Dual AI Analysis**: Uses both Ollama (Granite) and Qwen models for comprehensive project understanding
- **🎨 Visual Project Icons**: Generates unique colored icons for each project
- **🚀 One-Click Launching**: Launches projects in their proper environments with AI-generated commands
- **📱 Modern Web Interface**: Beautiful, responsive Gradio interface with multiple views
- **💾 Persistent Storage**: SQLite database stores all project metadata, launch commands, and analysis
- **🔄 Background Scanning**: Continuous monitoring for new projects and changes
- **⚡ Incremental Updates**: Only processes new or changed projects for efficiency
- **🏷️ Smart Caching**: Preserves AI-generated descriptions and launch commands
- **🛠️ Custom Launcher Creation**: Automatically creates editable custom launcher scripts
- **🌐 API Server**: RESTful API for external integrations
- **📊 Database Management UI**: Comprehensive database viewer and management interface

## 🆕 Latest Features

### AI Launch Command Generation (Qwen Integration)
- **Intelligent Analysis**: Qwen models analyze project structure, dependencies, and documentation
- **Multi-Option Analysis**: Provides primary launch method with alternatives when available
- **Custom Launcher Scripts**: Automatically creates editable bash scripts for complex projects
- **Confidence Scoring**: AI provides confidence levels for launch command recommendations
- **Fallback Systems**: Multiple fallback mechanisms ensure every project gets a launch method
- **User Override**: Easy custom launcher editing with template generation

### Unified Interface
- **Multiple Launch Modes**: Choose between persistent, enhanced, or database-focused interfaces
- **API Integration**: Full RESTful API for programmatic access
- **Database UI**: Comprehensive project database management and visualization
- **Command Line Options**: Flexible startup configuration with verbose logging

### Smart Project Management
- **Custom Launchers Directory**: User-editable launcher scripts in `custom_launchers/`
- **Force Re-analysis**: Re-run AI analysis for improved launch commands
- **Project Status Tracking**: Comprehensive status and health monitoring
- **Launch History**: Track successful launches and common patterns

## 🏗️ Architecture

The application uses a modular architecture with clear separation of concerns:

- **`launcher.py`** - Main launcher with full database integration, AI features, and unified interface
- **`qwen_launch_analyzer.py`** - **NEW**: AI-powered launch command generation using Qwen models
- **`database_ui.py`** - **NEW**: Comprehensive database management interface
- **`launch_api_server.py`** - **NEW**: RESTful API server for external integrations
- **`project_database.py`** - SQLite database management and operations
- **`background_scanner.py`** - Background scanning and incremental updates
- **`launcher_ui.py`** - Core UI components and project management logic
- **`project_scanner.py`** - Project discovery and identification
- **`environment_detector.py`** - Python environment detection
- **`ollama_summarizer.py`** - AI-powered project descriptions (Granite models)
- **`icon_generator.py`** - Visual icon generation
- **`logger.py`** - Comprehensive logging system
- **`enhanced_launcher.py`** - Legacy enhanced launcher (for comparison)
- **`app.py`** - Legacy simple launcher (for comparison)

## 📋 Requirements

- **Python 3.8+**
- **Ollama installed and running** (for project descriptions)
- **Ollama with Qwen models** (for launch command generation):
  - `qwen3:8b` (primary, fast analysis)
  - `qwen3:14b` (advanced analysis for complex projects)
- **Granite models** (for descriptions):
  - `granite3.1-dense:8b`
  - `granite-code:8b`
- **Linux environment** with `gnome-terminal` (for launching)

### Dependencies

```
gradio>=5.38.1
Pillow>=9.0.0
pathlib
pandas>=1.3.0
```

## 🚀 Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd ai-launcher
   pip install -r requirements.txt
   ```

2. **Install Required AI Models**
   ```bash
   # Qwen models for launch command generation
   ollama pull qwen3:8b
   ollama pull qwen3:14b
   
   # Granite models for project descriptions
   ollama pull granite3.1-dense:8b
   ollama pull granite-code:8b
   ```

3. **Create Configuration**
   Create a `config.json` file (ignored by git for privacy):
   ```json
   {
     "index_directories": [
       "/path/to/your/ai/projects",
       "/another/project/directory"
     ]
   }
   ```

4. **Launch the Application**
   ```bash
   ./launcher.sh
   ```
   
   Or choose your interface:
   ```bash
python3 launcher.py                    # Default: Main launcher
python3 launcher.py --mode database    # Database management UI
python3 launcher.py --mode api         # API server only
python3 launcher.py --verbose          # Verbose logging
```

5. **Access the Interface**
   - **Persistent Launcher**: http://localhost:7862
   - **Database UI**: http://localhost:7863
   - **API Server**: http://localhost:7864
   - **Enhanced Launcher**: http://localhost:7861 (legacy)

## 🎯 Usage

### First Run Experience
1. **Initial Discovery**: Comprehensive scan of your configured directories
2. **Database Creation**: Creates `projects.db` with all discovered projects
3. **AI Analysis**: Both Qwen and Granite models analyze projects in the background
4. **Custom Launcher Generation**: AI creates custom launcher scripts for each project
5. **Immediate Use**: Projects are immediately launchable with AI-generated commands

### AI Launch Command Generation
The system uses Qwen models to intelligently analyze each project:

1. **Structure Analysis**: Examines files, dependencies, and project layout
2. **Documentation Review**: Reads README files and comments for launch hints
3. **Pattern Recognition**: Identifies common project types and frameworks
4. **Command Generation**: Creates optimal launch commands with confidence scores
5. **Custom Launcher Creation**: Generates editable bash scripts in `custom_launchers/`
6. **Alternative Options**: Provides backup launch methods when multiple options exist

### Custom Launcher Scripts
Every project gets a custom launcher script:
- **Location**: `custom_launchers/<project-name>.sh`
- **Editable**: Fully customizable by users
- **AI-Generated**: Initially populated with AI analysis
- **Environment Variables**: Includes guidance for env var configuration
- **Executable**: Ready to run with proper permissions

### Project Management
- **Force Re-analysis**: Trigger new AI analysis for improved launch commands
- **Mark as Dirty**: Queue projects for re-processing
- **Manual Scanning**: Immediate directory scans for new projects
- **Database Management**: Full CRUD operations via database UI

## 🔧 Configuration

### Directory Configuration
Create `config.json` in the project root:
```json
{
  "index_directories": [
    "/media/user/AI/projects",
    "/home/user/git/ai-projects",
    "/opt/ml-projects"
  ]
}
```

### Database Configuration
- **Location**: `projects.db` (SQLite)
- **Auto-creation**: Database created on first run
- **Schema**: Projects, scan sessions, launch analytics, and metadata
- **Backup**: Recommended to backup `projects.db` periodically

### AI Model Configuration
The system automatically uses available models:
- **Qwen Models**: Primary for launch command generation
- **Granite Models**: Secondary for project descriptions
- **Fallback**: Heuristic analysis if AI models unavailable

### Scanning Configuration
- **Quick Scan**: Every 3 minutes (new projects)
- **Full Scan**: Every 60 minutes (comprehensive verification)
- **AI Re-analysis**: Every 24 hours (refresh launch commands)
- **Manual Triggers**: Available via UI buttons

## 🛠️ Advanced Features

### API Server
```bash
# Start API server
python3 launcher.py --mode api

# Example API calls
curl http://localhost:7864/api/projects                    # List all projects
curl http://localhost:7864/api/projects/scan               # Trigger scan
curl -X POST http://localhost:7864/api/projects/launch \
  -H "Content-Type: application/json" \
  -d '{"project_path": "/path/to/project"}'               # Launch project
```

### Database Management
```bash
# View all projects
sqlite3 projects.db "SELECT name, launch_command, launch_confidence FROM projects;"

# Force re-analysis
sqlite3 projects.db "UPDATE projects SET dirty_flag = 1;"

# View launch analytics
sqlite3 projects.db "SELECT * FROM scan_sessions ORDER BY start_time DESC LIMIT 10;"

# Custom launcher usage
sqlite3 projects.db "SELECT name, launch_type FROM projects WHERE launch_type = 'custom_launcher';"
```

### Custom Launcher Management
```bash
# List all custom launchers
ls custom_launchers/

# Edit a custom launcher
nano custom_launchers/my-project.sh

# Test a custom launcher
./custom_launchers/my-project.sh

# Force regeneration of custom launcher
# (Use "Force Re-analyze" button in UI)
```

### Advanced Logging
- **Application Log**: `logs/ai_launcher.log`
- **Ollama Transactions**: `logs/ollama_transactions.log`
- **API Access Log**: `logs/api_access.log`
- **Launch History**: Tracked in database

## 🧪 Testing and Development

### Component Testing
```bash
# Test Qwen launch analyzer (if available)
# Note: test files are excluded from git for privacy
python3 -c "from qwen_launch_analyzer import QwenLaunchAnalyzer; print('OK')"

# Test database operations
python3 -c "from project_database import db; print(db.get_stats())"

# Test project scanning
python3 -c "from project_scanner import ProjectScanner; print('OK')"
```

### Icon Generation Test
```bash
python3 icon_generator.py
```

### Database Inspection
```bash
# View database structure
sqlite3 projects.db ".schema"

# Check project count
sqlite3 projects.db "SELECT COUNT(*) FROM projects;"

# View recent AI analysis
sqlite3 projects.db "SELECT name, launch_analysis_method, launch_confidence FROM projects WHERE launch_analyzed_at > strftime('%s', 'now', '-1 day');"
```

## 📁 Project Structure

```
ai-launcher/
├── launcher.py                   # Main launcher with full AI features and unified interface
├── qwen_launch_analyzer.py       # NEW: AI launch command generation
├── database_ui.py               # NEW: Database management interface
├── launch_api_server.py          # NEW: RESTful API server
├── project_database.py          # Database management and operations
├── background_scanner.py         # Background scanning and updates
├── launcher_ui.py               # Core UI components
├── project_scanner.py           # Project discovery logic
├── environment_detector.py      # Environment detection
├── ollama_summarizer.py         # AI project descriptions
├── icon_generator.py            # Icon generation
├── logger.py                    # Comprehensive logging
├── launch.py                    # Launch utilities
├── enhanced_launcher.py         # Legacy enhanced version
├── app.py                       # Legacy simple launcher
├── launcher.sh                  # Launch script
├── config.json                  # Configuration (git-ignored)
├── requirements.txt             # Python dependencies
├── projects.db                  # SQLite database (created at runtime)
├── custom_launchers/            # Custom launcher scripts (git-ignored)
│   ├── project1.sh
│   ├── project2.sh
│   └── ...
├── logs/                        # Log files (git-ignored)
│   ├── ai_launcher.log
│   ├── ollama_transactions.log
│   └── api_access.log
└── README.md                    # This file
```

## 🎨 Features in Detail

### AI-Powered Launch Commands
Each project receives intelligent analysis:
- **Multi-Model Analysis**: Qwen models analyze structure and documentation
- **Confidence Scoring**: AI provides 0.0-1.0 confidence ratings
- **Alternative Methods**: Multiple launch options when available
- **Custom Script Generation**: Editable bash scripts for complex setups
- **Environment Integration**: Automatic environment activation
- **Pattern Recognition**: Recognizes common frameworks and tools

### Project Cards
Each project displays:
- **Unique Icon**: Generated with consistent colors
- **Environment Badge**: Shows detected Python environment
- **Status Indicators**: Up-to-date status, git repository, AI confidence
- **Launch Information**: AI-generated command and confidence level
- **Custom Launcher**: Indicates if custom script is available
- **Last Analysis**: Timestamp of AI analysis

### Smart Environment Handling
The launcher automatically:
- **Detects Environment**: Identifies conda, venv, poetry, pipenv
- **Activates Environment**: Sets up environment before launching
- **Finds Entry Points**: Identifies main scripts and executables
- **Handles Complex Projects**: Supports nested structures and frameworks
- **Creates Custom Scripts**: Generates bash scripts for complex setups

## 🚀 Interface Comparison

| Feature | Legacy (`app.py`) | Enhanced (`enhanced_launcher.py`) | **Main Launcher (`launcher.py`)** |
|---------|------------------|-----------------------------------|-------------------------------------------|-------------------------------------|
| AI Launch Commands | None | None | **Qwen-powered** | **Qwen-powered** |
| Project Discovery | Manual scan | Manual/Auto scan | **Background + Manual** | **Background + Manual** |
| Database Storage | None | None | **SQLite with history** | **SQLite with history** |
| Custom Launchers | None | None | **Auto-generated** | **Auto-generated** |
| API Server | None | None | Optional | **Integrated** |
| Database UI | None | None | Separate | **Integrated** |
| Multiple Interfaces | No | No | No | **Yes** |
| Session Persistence | None | None | **Full persistence** | **Full persistence** |
| Port | 7860 | 7861 | 7862 | **7862-7864** |

## 🐛 Troubleshooting

### Common Issues

1. **AI Models Not Available**: Install Qwen and Granite models via Ollama
2. **Custom Launchers Not Working**: Check permissions: `chmod +x custom_launchers/*.sh`
3. **Database Errors**: Delete `projects.db` to reset (requires full rescan)
4. **Background Scanner Issues**: Check logs for threading or permission errors
5. **Launch Command Failures**: Edit custom launcher scripts in `custom_launchers/`

### AI Analysis Issues

- **Low Confidence**: Try "Force Re-analyze" or edit custom launcher script
- **Wrong Commands**: Edit the generated script in `custom_launchers/`
- **Missing Models**: Ensure Qwen models are installed: `ollama list`
- **Timeout Errors**: Check Ollama service: `ollama serve`

### Performance Optimization

- **Large Directories**: Consider excluding non-project subdirectories
- **AI Performance**: Ensure sufficient RAM for Qwen models (8GB+ recommended)
- **Database Size**: Regularly cleanup old scan sessions
- **Custom Launchers**: Use custom scripts for consistently problematic projects

### Debug Mode

Enable detailed logging:
```bash
# Verbose logging
python3 launcher.py --verbose

# View real-time logs
tail -f logs/ai_launcher.log

# View AI model interactions
tail -f logs/ollama_transactions.log

# Database inspection
sqlite3 projects.db ".tables"
```

## 🤝 Contributing

1. Follow the cursor rules for project structure
2. Keep UI components in feature modules (`*_ui.py`)
3. Maintain separation between core logic and UI
4. Add comprehensive logging for new features
5. Test AI integrations with fallback mechanisms
6. Update database schema carefully (consider migrations)
7. Document new API endpoints

## 📝 License

This project is open source. See LICENSE file for details.

## 🙏 Acknowledgments

- Built with [Gradio](https://gradio.app/) for responsive web interfaces
- Uses [Ollama](https://ollama.ai/) for local AI inference
- Powered by **Qwen models** for intelligent launch command generation
- Enhanced with **IBM Granite models** for project descriptions
- SQLite for efficient local storage and persistence
- Threading and async patterns for responsive background processing 