import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_domain_models_are_immutable() -> None:
    model_files = (
        PROJECT_ROOT / "src/trajcert/domain/identity.py",
        PROJECT_ROOT / "src/trajcert/domain/manifests.py",
        PROJECT_ROOT / "src/trajcert/domain/operational.py",
    )
    for model_file in model_files:
        tree = ast.parse(model_file.read_text(encoding="utf-8"))
        classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        assert classes
        assert all(
            any(
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Name)
                and decorator.func.id == "dataclass"
                and any(
                    isinstance(keyword.value, ast.Constant)
                    and keyword.arg == "frozen"
                    and keyword.value.value is True
                    for keyword in decorator.keywords
                )
                for decorator in class_node.decorator_list
            )
            or any(
                isinstance(base, ast.Name) and base.id == "BaseModel" for base in class_node.bases
            )
            or any(isinstance(base, ast.Name) and base.id == "StrEnum" for base in class_node.bases)
            for class_node in classes
        )
