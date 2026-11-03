import ast


def suggest_tests(code: str) -> list[str]:
    """Suggest test names from public functions; does not execute submitted code."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ["test_submitted_code_has_valid_python_syntax"]

    names = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    if not names:
        return [
            "test_module_imports_without_errors",
            "test_expected_public_behaviour",
            "test_invalid_input_is_handled",
        ]

    suggestions = []
    for name in names[:20]:
        suggestions.extend(
            [
                f"test_{name}_with_valid_input",
                f"test_{name}_with_invalid_input",
                f"test_{name}_edge_cases",
            ]
        )
    return suggestions
