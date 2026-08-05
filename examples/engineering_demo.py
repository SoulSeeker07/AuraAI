"""
Example: Using the Engineering Intelligence Platform

This example demonstrates how to use the Engineering Intelligence Platform
to understand and manipulate code at the architectural level.
"""

from pathlib import Path

from src.engineering import EngineeringManager


def main():
    # Initialize the Engineering Manager
    # This connects to existing Aura AI systems
    manager = EngineeringManager(
        repository_path=Path("d:/Sreekanta/VS Code Project/Desktop AI/AuraAI"),
        knowledge_manager=None,  # Replace with actual knowledge manager
        memory_manager=None,  # Replace with actual memory manager
        workspace_manager=None,  # Replace with actual workspace manager
        agent_runtime=None,  # Replace with actual agent runtime
        tool_execution_engine=None,  # Replace with actual tool execution engine
    )

    print("=== Engineering Intelligence Platform Demo ===\n")

    # 1. Repository Analysis
    print("1. Repository Analysis")
    repo_state = manager.sync_repository()
    print(f"   Repository: {repo_state.name}")
    print(f"   Language: {repo_state.language}")
    print(f"   Framework: {repo_state.framework}")
    print(f"   Health Score: {repo_state.get_health_score()}/100")
    print(f"   Health: {repo_state.health.value}")
    print()

    # 2. AST Analysis
    print("2. AST Analysis")
    print("   Understanding src/main.py...")
    ast_file = manager.understand_code("src/main.py")
    print(f"   - Language: {ast_file.language}")
    print(f"   - Lines: {ast_file.line_count}")
    print(f"   - Classes: {len(ast_file.classes)}")
    print(f"   - Functions: {len(ast_file.functions)}")
    print(f"   - Imports: {len(ast_file.imports)}")
    print()

    # 3. Symbol Graph
    print("3. Symbol Graph")
    symbols = manager.get_all_symbols("src/main.py")
    print(f"   Total symbols: {len(symbols)}")
    for i, symbol in enumerate(symbols[:5]):  # Show first 5
        print(f"   - {symbol['name']} ({symbol['type']})")
    print()

    # 4. Planning
    print("4. Engineering Planning")
    print("   Planning a refactoring...")
    plan = manager.plan_refactoring(
        old_name="old_function",
        new_name="new_function",
        operation="rename",
        context={"file_path": "src/main.py"},
    )
    print(f"   - Operation: {plan['operation']}")
    print(f"   - Affected files: {len(plan['affected_files'])}")
    print(f"   - Estimated time: {plan['estimated_time']}")
    print(f"   - Risk level: {plan['risk_level']}")
    print()

    # 5. Code Quality
    print("5. Code Quality Report")
    quality = manager.get_quality_report()
    print(f"   Overall score: {quality['overall_score']}")
    print(f"   Metrics: {len(quality['metrics'])}")
    print(f"   Warnings: {len(quality['warnings'])}")
    print(f"   Recommendations: {len(quality['recommendations'])}")
    print()

    # 6. Documentation Generation
    print("6. Documentation Generation")
    doc_result = manager.generate_documentation(target="README.md", format="markdown")
    if doc_result["success"]:
        print(f"   Generated: {doc_result['file_path']}")
    print()

    # 7. Git Intelligence
    print("7. Git Intelligence")
    git_status = manager.get_git_status()
    print(f"   Branch: {git_status['branch']}")
    print(f"   Working directory clean: {git_status['working_dir_clean']}")
    print(f"   Staged changes: {git_status['staged']}")
    print()

    # 8. Dashboard
    print("8. Project Dashboard")
    dashboard = manager.get_dashboard()
    print(f"   Overall health: {dashboard['overall_health']}")
    print(f"   Health score: {dashboard['health_score']}")
    print(f"   Quality score: {dashboard['quality']['overall_score']}")
    print(f"   Architecture score: {dashboard['architecture_score']}")
    print(f"   Recommendations: {len(dashboard['recommendations'])}")
    print()

    print("=== Demo Complete ===")


if __name__ == "__main__":
    main()
