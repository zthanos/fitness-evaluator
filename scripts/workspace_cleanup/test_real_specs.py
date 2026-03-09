"""Test the evaluate_specs_content method with real specs files."""

import sys
from pathlib import Path

# Add the workspace root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.workspace_cleanup.code_analyzer import CodeAnalyzer


def test_real_specs_evaluation():
    """Test evaluation of actual specs/plan.md and specs/taks.md files."""
    workspace_root = Path.cwd()
    analyzer = CodeAnalyzer(workspace_root)
    
    # Test specs/plan.md
    plan_file = workspace_root / "specs" / "plan.md"
    if plan_file.exists():
        print("\n=== Evaluating specs/plan.md ===")
        result = analyzer.evaluate_specs_content(plan_file)
        print(f"Has value: {result.has_value}")
        print(f"Reason: {result.reason}")
        print(f"Recommended action: {result.recommended_action}")
    else:
        print("specs/plan.md not found")
    
    # Test specs/taks.md
    taks_file = workspace_root / "specs" / "taks.md"
    if taks_file.exists():
        print("\n=== Evaluating specs/taks.md ===")
        result = analyzer.evaluate_specs_content(taks_file)
        print(f"Has value: {result.has_value}")
        print(f"Reason: {result.reason}")
        print(f"Recommended action: {result.recommended_action}")
    else:
        print("specs/taks.md not found")


if __name__ == "__main__":
    test_real_specs_evaluation()
