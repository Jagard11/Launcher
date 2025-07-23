# 🚀 AI Project Launcher

A sophisticated Gradio-based application that automatically discovers, categorizes, and launches AI/ML projects from specified directories. Features intelligent environment detection, AI-powered project descriptions using Ollama with Granite models, one-click project launching, **persistent caching**, and **background scanning**.

## ✨ Features

- **🔍 Automatic Project Discovery**: Scans specified directories for AI/ML projects
- **🐍 Environment Detection**: Automatically detects Python environments (conda, venv, poetry, pipenv)
- **🤖 AI-Powered Descriptions**: Uses Ollama with Granite models to generate project summaries
- **🎨 Visual Project Icons**: Generates unique colored icons for each project
- **🚀 One-Click Launching**: Launches projects in their proper environments
- **📱 Modern Web Interface**: Beautiful, responsive Gradio interface
- **💾 Persistent Storage**: SQLite database stores project metadata between sessions
- **🔄 Background Scanning**: Continuous monitoring for new projects and changes
- **⚡ Incremental Updates**: Only processes new or changed projects
- **🏷️ Smart Caching**: Preserves AI-generated descriptions and metadata

## 🆕 **New Persistent Features**

### Background Scanning
- **Automatic Discovery**: Continuously scans for new projects every 5 minutes
- **Full Scans**: Complete directory traversal every hour
- **Smart Detection**: Only processes projects that have actually changed
- **Real-time Updates**: New projects appear automatically in the UI

### Persistent Database
- **SQLite Storage**: All project metadata stored in `projects.db`
- **Session Persistence**: No need to rescan projects between app restarts
- **Dirty Flag System**: Track which projects need AI re-analysis
- **Scan History**: Complete audit trail of scanning sessions

### Manual Controls
- **Manual Scan**: Force immediate directory scan
- **Process Updates**: Trigger AI analysis for projects marked as dirty
- **Mark as Dirty**: Force re-analysis of specific projects
- **Refresh UI**: Reload data from database

## 🏗️ Architecture

The application follows a modular architecture with clear separation of concerns:

- **`persistent_launcher.py`** - **NEW**: Main launcher with database integration and background scanning
- **`enhanced_launcher.py`** - Previous version for comparison
- **`app.py`** - Legacy simple launcher
- **`project_database.py`** - **NEW**: SQLite database management
- **`background_scanner.py`** - **NEW**: Background scanning and incremental updates
- **`launcher_ui.py`** - Core UI components and project management logic
- **`project_scanner.py`** - Discovers and identifies AI/ML projects
- **`environment_detector.py`** - Detects Python environments for each project
- **`ollama_summarizer.py`** - Generates AI-powered project descriptions
- **`icon_generator.py`** - Creates unique visual icons for projects
- **`logger.py`** - **NEW**: Comprehensive logging system

## 📋 Requirements

- Python 3.8+
- Ollama installed and running
- Granite models: `granite3.1-dense:8b` and `granite-code:8b`
- Linux environment with `gnome-terminal`

### Dependencies

```
gradio>=4.0.0
Pillow>=9.0.0
```

## 🚀 Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd ai-launcher
   pip install -r requirements.txt
   ```

2. **Install Ollama Models**
   ```bash
   ollama pull granite3.1-dense:8b
   ollama pull granite-code:8b
   ```

3. **Configure Directories**
   Edit `config.json` to specify your project directories:
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
   
   Or manually:
   ```bash
   python3 persistent_launcher.py    # Recommended: Full persistent features
   python3 enhanced_launcher.py     # Alternative: Session-based
   ```

5. **Access the Interface**
   - **Persistent Launcher**: http://localhost:7862
   - **Enhanced Launcher**: http://localhost:7861

## 🎯 Usage

### First Run Experience
1. **Initial Scan**: The app performs a comprehensive scan of your directories
2. **Database Creation**: Creates `projects.db` with all discovered projects
3. **Background Processing**: AI descriptions generated in the background
4. **Immediate Use**: Projects are immediately launchable

### Subsequent Runs
1. **Instant Load**: Projects load immediately from the database
2. **Background Updates**: Scanner continues monitoring for changes
3. **Incremental Processing**: Only new/changed projects are analyzed
4. **Persistent State**: All settings and metadata preserved

### Project Discovery

The scanner looks for directories containing:
- Python files (`.py`)
- AI/ML indicators (requirements.txt, model files, etc.)
- Common AI frameworks (torch, tensorflow, gradio, etc.)
- Nested project structures (automatically detected)

### Environment Detection

Supports automatic detection of:
- **Conda environments** (`environment.yml`, named environments)
- **Virtual environments** (`venv/`, `env/`, `.venv/`)
- **Poetry** (`pyproject.toml`)
- **Pipenv** (`Pipfile`)
- **Requirements.txt** (fallback to system Python)

### AI-Powered Intelligence

Uses multiple Granite models for comprehensive analysis:
- **`granite3.1-dense:8b`**: Document summarization and final description generation
- **`granite-code:8b`**: Code analysis and technical summaries
- **Smart Caching**: Descriptions preserved between sessions
- **Incremental Updates**: Only re-analyze when marked as dirty

## 🔧 Configuration

### `config.json`
```json
{
  "index_directories": [
    "/media/user/AI/projects",
    "/home/user/git/ai-projects"
  ]
}
```

### Database Configuration
- **Location**: `projects.db` (SQLite)
- **Auto-creation**: Database created on first run
- **Schema**: Projects, scan sessions, and metadata tables
- **Backup**: Recommended to backup `projects.db` periodically

### Scanning Intervals
- **Quick Scan**: Every 5 minutes (new projects only)
- **Full Scan**: Every 60 minutes (complete verification)
- **Manual Triggers**: Available via UI buttons

## 🛠️ Advanced Features

### Database Management
```bash
# View database contents
sqlite3 projects.db "SELECT name, environment_type, status FROM projects;"

# Mark all projects as dirty
sqlite3 projects.db "UPDATE projects SET dirty_flag = 1;"

# View scan history
sqlite3 projects.db "SELECT * FROM scan_sessions ORDER BY start_time DESC LIMIT 10;"
```

### Manual Project Management
- **Mark as Dirty**: Force re-analysis via UI
- **Environment Override**: Edit database directly if needed
- **Bulk Operations**: Use SQL commands for batch updates

### Logging
- **Application Log**: `logs/ai_launcher.log`
- **Ollama Transactions**: `logs/ollama_transactions.log`
- **Console Output**: Real-time status updates

## 🧪 Testing

Run component tests:
```bash
python3 test_app.py        # Test core components
python3 debug_scanner.py   # Debug project discovery
python3 test_launch.py     # Test launch functionality
```

Test icon generation:
```bash
python3 icon_generator.py
```

Test database operations:
```bash
python3 -c "from project_database import db; print(db.get_stats())"
```

## 📁 Project Structure

```
ai-launcher/
├── persistent_launcher.py     # NEW: Main persistent launcher
├── project_database.py        # NEW: Database management
├── background_scanner.py      # NEW: Background scanning
├── logger.py                  # NEW: Comprehensive logging
├── enhanced_launcher.py       # Previous enhanced version
├── app.py                     # Legacy simple launcher
├── launcher_ui.py             # Core UI components
├── project_scanner.py         # Project discovery logic
├── environment_detector.py    # Environment detection
├── ollama_summarizer.py       # AI-powered summaries
├── icon_generator.py          # Icon generation
├── launcher.sh               # Launch script
├── config.json              # Configuration
├── requirements.txt          # Dependencies
├── projects.db              # SQLite database (created on first run)
├── logs/                    # Log files
│   ├── ai_launcher.log
│   └── ollama_transactions.log
└── README.md               # This file
```

## 🎨 Features in Detail

### Project Cards
Each project displays:
- Unique generated icon with consistent colors
- Project name and environment type
- Status badges (Up to Date/Needs Update, Git repository)
- AI-generated description
- Last scan timestamp
- Environment and main script information

### Smart Environment Handling
The launcher automatically:
- Detects the appropriate Python environment
- Activates the environment before launching
- Finds the main script (supports nested projects)
- Opens a new terminal with the running application
- Handles complex project structures (e.g., Stable Diffusion with nested webui)

### Background Intelligence
- **Continuous Monitoring**: Watches for new projects and changes
- **Efficient Processing**: Only analyzes what's actually changed
- **Persistent Metadata**: Descriptions and analysis cached indefinitely
- **Manual Override**: Force re-analysis when needed

## 🚀 Version Comparison

| Feature | Legacy (`app.py`) | Enhanced (`enhanced_launcher.py`) | **Persistent (`persistent_launcher.py`)** |
|---------|------------------|-----------------------------------|-------------------------------------------|
| Project Discovery | Manual scan | Manual/Auto scan | **Background + Manual** |
| Database Storage | None | None | **SQLite with full history** |
| AI Descriptions | On-demand | On-demand | **Cached + Background processing** |
| Session Persistence | None | None | **Full persistence** |
| Incremental Updates | None | None | **Smart dirty tracking** |
| Launch Functionality | Basic | Enhanced | **Enhanced + Logging** |
| UI Updates | Static | Dynamic | **Real-time + Status tracking** |
| Port | 7860 | 7861 | **7862** |

## 🐛 Troubleshooting

### Common Issues

1. **Database Errors**: Delete `projects.db` to reset (will require full rescan)
2. **Background Scanner Not Working**: Check logs for threading issues
3. **Projects Not Updating**: Try "Manual Scan" or "Process Updates" buttons
4. **Ollama Connection**: Ensure Ollama is running (`ollama serve`)
5. **Permission Errors**: Check directory access permissions

### Performance Optimization

- **Database Size**: Regularly cleanup old scan sessions
- **Ollama Performance**: Ensure sufficient RAM for models
- **Directory Size**: Very large directories may slow initial scans
- **Concurrent Limits**: Background processing limited to 3 parallel Ollama calls

### Debug Mode

Enable detailed logging:
```bash
# View real-time logs
tail -f logs/ai_launcher.log

# View Ollama transactions
tail -f logs/ollama_transactions.log

# Database inspection
sqlite3 projects.db ".tables"
```

## 🤝 Contributing

1. Follow the cursor rules for project structure
2. Keep UI components in feature modules
3. Maintain separation between core logic and UI
4. Add tests for new features
5. Update database schema carefully (consider migrations)

## 📝 License

This project is open source. See LICENSE file for details.

## 🙏 Acknowledgments

- Built with [Gradio](https://gradio.app/) for the web interface
- Uses [Ollama](https://ollama.ai/) for local AI inference
- Powered by IBM's Granite models for code and document analysis
- SQLite for efficient local storage
- Threading and async patterns for responsive UI 