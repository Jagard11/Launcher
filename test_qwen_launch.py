#!/usr/bin/env python3

import json
from pathlib import Path
from qwen_launch_analyzer import QwenLaunchAnalyzer
from project_database import db
import time

def test_launch_analyzer():
    """Test the Qwen launch analyzer on a few example projects"""
    
    print("🧪 Testing Qwen Launch Analyzer...")
    
    analyzer = QwenLaunchAnalyzer()
    
    # Get some projects from the database to test
    projects = db.get_all_projects(active_only=True)[:5]  # Test first 5 projects
    
    if not projects:
        print("❌ No projects found in database")
        return
    
    print(f"🔍 Testing on {len(projects)} projects...")
    
    for i, project in enumerate(projects, 1):
        project_name = project['name']
        project_path = project['path']
        env_type = project.get('environment_type', 'none')
        env_name = project.get('environment_name', '')
        
        print(f"\n{'='*50}")
        print(f"Test {i}: {project_name}")
        print(f"Path: {project_path}")
        print(f"Environment: {env_type} ({env_name})")
        print(f"{'='*50}")
        
        if not Path(project_path).exists():
            print("❌ Project path doesn't exist, skipping...")
            continue
        
        try:
            # Test structure analysis
            print("📁 Analyzing project structure...")
            structure = analyzer.analyze_project_structure(project_path)
            
            print(f"  Python files: {structure['python_files'][:3]}...")
            print(f"  Config files: {structure['config_files'][:3]}...")
            print(f"  Requirements: {structure['requirements'][:3]}...")
            print(f"  Has Docker: {structure['dockerfile']}")
            print(f"  Has Scripts: {len(structure['scripts'])} scripts")
            
            # Test launch command generation
            print("\n🚀 Generating launch command...")
            start_time = time.time()
            
            launch_analysis = analyzer.generate_launch_command(
                project_path, project_name, env_type, env_name
            )
            
            analysis_time = time.time() - start_time
            
            print(f"⏱️  Analysis completed in {analysis_time:.2f} seconds")
            print(f"🎯 Method: {launch_analysis.get('analysis_method', 'unknown')}")
            print(f"📊 Confidence: {launch_analysis.get('confidence', 0.0):.2f}")
            print(f"🏷️  Type: {launch_analysis.get('launch_type', 'unknown')}")
            print(f"📄 Main Script: {launch_analysis.get('main_script', 'unknown')}")
            print(f"💻 Command: {launch_analysis.get('launch_command', 'unknown')}")
            print(f"📁 Working Dir: {launch_analysis.get('working_directory', '.')}")
            print(f"📝 Notes: {launch_analysis.get('notes', 'None')}")
            
            # Check if it looks reasonable
            command = launch_analysis.get('launch_command', '')
            confidence = launch_analysis.get('confidence', 0.0)
            
            if confidence >= 0.7:
                print("✅ High confidence result!")
            elif confidence >= 0.5:
                print("⚠️  Medium confidence result")
            else:
                print("❌ Low confidence result")
            
            if 'python' in command.lower() or command in ['streamlit run', 'docker']:
                print("✅ Command looks reasonable")
            else:
                print("⚠️  Command may need review")
                
        except Exception as e:
            print(f"❌ Error testing {project_name}: {e}")
            import traceback
            print(traceback.format_exc())
        
        print("\n" + "="*50)

def test_database_integration():
    """Test database integration for launch commands"""
    
    print("\n🗄️  Testing Database Integration...")
    
    # Get a project and check if it has launch command data
    projects = db.get_all_projects(active_only=True)
    
    projects_with_launch = [p for p in projects if p.get('launch_command')]
    projects_without_launch = [p for p in projects if not p.get('launch_command')]
    
    print(f"📊 Projects with AI launch commands: {len(projects_with_launch)}")
    print(f"📊 Projects without AI launch commands: {len(projects_without_launch)}")
    
    if projects_with_launch:
        print("\n✅ Sample project with AI launch command:")
        sample = projects_with_launch[0]
        print(f"  Name: {sample['name']}")
        print(f"  Command: {sample.get('launch_command', 'None')}")
        print(f"  Type: {sample.get('launch_type', 'unknown')}")
        print(f"  Confidence: {sample.get('launch_confidence', 0.0):.2f}")
    
    if projects_without_launch:
        print(f"\n⚠️  {len(projects_without_launch)} projects need AI analysis")
        print("   Run the background scanner to generate launch commands for these projects.")

def main():
    """Main test function"""
    print("🚀 Qwen Launch Analyzer Test Suite")
    print("=" * 60)
    
    try:
        # Test the analyzer
        test_launch_analyzer()
        
        # Test database integration
        test_database_integration()
        
        print("\n✅ Test suite completed!")
        print("\nNext steps:")
        print("1. Run the background scanner to process all projects")
        print("2. Launch the persistent launcher to test the AI-powered launch functionality")
        print("3. Check that launch buttons work with the new AI commands")
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    main() 