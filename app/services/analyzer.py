import ast
import re
from app.schemas.review import Finding

SECRET_PATTERNS = [
    (re.compile(r"""(?i)(api[_-]?key|secret|password|token)\s*=\s*['"][^'"]{8,}['"]"""),
     "Possible hard-coded credential"),
]

def analyze_python(code: str) -> list[Finding]:
    findings: list[Finding] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [Finding(
            rule_id="PY-SYNTAX-001", severity="high",
            title="Python syntax error",
            message=exc.msg, line=exc.lineno,
            recommendation="Correct the syntax error before running or testing this file."
        )]

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr

            if name in {"eval", "exec"}:
                findings.append(Finding(
                    rule_id="PY-SEC-001", severity="high",
                    title=f"Use of {name}()",
                    message=f"{name}() can execute dynamically supplied code.",
                    line=getattr(node, "lineno", None),
                    recommendation="Avoid dynamic code execution. Use explicit parsing or a restricted mapping of allowed operations."
                ))

            if name in {"system", "popen"}:
                findings.append(Finding(
                    rule_id="PY-SEC-003", severity="high",
                    title=f"Potential shell execution via {name}()",
                    message="Shell or process execution can be dangerous when arguments contain untrusted input.",
                    line=getattr(node, "lineno", None),
                    recommendation="Avoid shell execution where possible. Prefer subprocess APIs with argument lists and validate all inputs."
                ))

            if name == "loads" and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "pickle":
                    findings.append(Finding(
                        rule_id="PY-SEC-004", severity="critical",
                        title="Unsafe pickle deserialization",
                        message="Unpickling untrusted data can execute arbitrary code.",
                        line=getattr(node, "lineno", None),
                        recommendation="Never unpickle untrusted data. Prefer safer formats such as JSON."
                    ))

            if name == "load" and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "yaml":
                    findings.append(Finding(
                        rule_id="PY-SEC-005", severity="high",
                        title="Potential unsafe YAML loading",
                        message="yaml.load() can construct arbitrary Python objects depending on loader configuration.",
                        line=getattr(node, "lineno", None),
                        recommendation="Use yaml.safe_load() for untrusted YAML input."
                    ))

            if name == "open" and len(node.args) >= 2:
                mode = node.args[1]
                if isinstance(mode, ast.Constant) and isinstance(mode.value, str) and "w" in mode.value:
                    findings.append(Finding(
                        rule_id="PY-IO-001", severity="info",
                        title="File write operation",
                        message="This code writes to a file; verify the target path and permissions.",
                        line=getattr(node, "lineno", None),
                        recommendation="Validate file paths and avoid writing to locations supplied directly by untrusted users."
                    ))

        if isinstance(node, ast.ExceptHandler) and node.type is None:
            findings.append(Finding(
                rule_id="PY-QUAL-001", severity="medium",
                title="Bare except clause",
                message="A bare except catches every exception, including system-exiting exceptions.",
                line=getattr(node, "lineno", None),
                recommendation="Catch specific exception types and handle them deliberately."
            ))

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_line = getattr(node, "end_lineno", node.lineno)
            length = end_line - node.lineno + 1
            if length > 50:
                findings.append(Finding(
                    rule_id="PY-MAINT-001", severity="low",
                    title="Long function",
                    message=f"Function '{node.name}' spans approximately {length} lines.",
                    line=node.lineno,
                    recommendation="Consider extracting cohesive operations into smaller functions."
                ))

    for pattern, title in SECRET_PATTERNS:
        for match in pattern.finditer(code):
            line = code.count("\n", 0, match.start()) + 1
            findings.append(Finding(
                rule_id="PY-SEC-002", severity="critical",
                title=title,
                message="A value resembling a credential appears to be assigned directly in source code.",
                line=line,
                recommendation="Remove the value from source control, rotate the credential if real, and load secrets from environment variables or a secret manager."
            ))


    # Catch disabled TLS certificate verification in common requests calls.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "verify" and isinstance(keyword.value, ast.Constant) and keyword.value.value is False:
                    findings.append(Finding(
                        rule_id="PY-SEC-006", severity="high",
                        title="TLS certificate verification disabled",
                        message="A network request disables TLS certificate verification.",
                        line=getattr(node, "lineno", None),
                        recommendation="Keep certificate verification enabled. Fix the trust store or certificate configuration instead."
                    ))

    return findings


# Lightweight, language-aware pattern checks. These are heuristics, not parsers.
LANGUAGE_RULES = {
    "javascript": [
        (r"\beval\s*\(", "high", "JS-SEC-001", "Dynamic code execution", "Avoid eval(); use explicit parsing or a safe dispatch map."),
        (r"\binnerHTML\s*=", "high", "JS-SEC-002", "Potential unsafe HTML injection", "Prefer textContent or sanitize untrusted HTML with a maintained sanitizer."),
        (r"\bnew\s+Function\s*\(", "high", "JS-SEC-003", "Dynamic Function constructor", "Avoid constructing executable code from strings."),
        (r"\b(child_process\.)?(exec|execSync)\s*\(", "high", "JS-SEC-004", "Shell command execution", "Avoid shell command construction; use argument arrays and validate inputs."),
        (r"\bhttps?://[^\s'\"]+", "info", "JS-QUAL-001", "Hard-coded URL", "Confirm environment-specific endpoints are configurable."),
    ],
    "typescript": [
        (r"\bas\s+any\b|:\s*any\b", "low", "TS-QUAL-001", "Use of any type", "Prefer a concrete type, unknown, or a validated generic."),
        (r"\beval\s*\(", "high", "TS-SEC-001", "Dynamic code execution", "Avoid eval(); use explicit parsing or a safe dispatch map."),
        (r"\binnerHTML\s*=", "high", "TS-SEC-002", "Potential unsafe HTML injection", "Prefer textContent or sanitize untrusted HTML."),
        (r"\bnew\s+Function\s*\(", "high", "TS-SEC-003", "Dynamic Function constructor", "Avoid constructing executable code from strings."),
    ],
    "java": [
        (r"\bRuntime\.getRuntime\(\)\.exec\s*\(", "high", "JAVA-SEC-001", "Process execution", "Avoid shell/process execution with untrusted input; validate arguments and use safer APIs."),
        (r"\bStatement\s*\.execute(Query|Update)?\s*\(\s*\w+\s*\+", "high", "JAVA-SEC-002", "Possible SQL concatenation", "Use PreparedStatement parameters instead of concatenating SQL."),
        (r"\bnew\s+ObjectInputStream\s*\(", "high", "JAVA-SEC-003", "Java native deserialization", "Do not deserialize untrusted streams; use constrained formats and filters."),
        (r"\bprintStackTrace\s*\(\s*\)", "low", "JAVA-QUAL-001", "Direct stack trace output", "Use structured logging and avoid exposing internal details to users."),
    ],
    "php": [
        (r"\b(eval|assert)\s*\(", "high", "PHP-SEC-001", "Dynamic code evaluation", "Avoid evaluating dynamically supplied strings."),
        (r"\b(exec|shell_exec|system|passthru)\s*\(", "high", "PHP-SEC-002", "Shell command execution", "Avoid shell commands with untrusted input; use safe APIs and strict validation."),
        (r"\b(unserialize)\s*\(", "high", "PHP-SEC-003", "Potential unsafe deserialization", "Avoid unserializing untrusted data; use JSON or strict allowed_classes settings."),
        (r"\bmysql_query\s*\(", "high", "PHP-SEC-004", "Legacy database API", "Use PDO or MySQLi with prepared statements."),
        (r"\$_(GET|POST|REQUEST)\s*\[[^]]+\].{0,80}(echo|print)", "medium", "PHP-SEC-005", "Potential reflected output", "Escape untrusted values for the output context."),
    ],
    "sql": [
        (r"\bDROP\s+(TABLE|DATABASE)\b", "high", "SQL-SEC-001", "Destructive DDL statement", "Confirm destructive statements are intentional and protected by migration/review controls."),
        (r"\bWHERE\b[^;\n]*\bOR\b[^;\n]*=\s*['\"]?['\"]?", "medium", "SQL-SEC-002", "Broad OR predicate", "Review predicate logic; tautologies can unintentionally widen affected rows."),
        (r"\bSELECT\s+\*\b", "low", "SQL-QUAL-001", "Wildcard column selection", "Select only required columns to reduce coupling and data exposure."),
        (r"\bUPDATE\s+\w+\s+SET\b(?![^;\n]*\bWHERE\b)", "high", "SQL-SEC-003", "UPDATE without WHERE", "Verify whether the update should affect every row; use a transaction and scoped predicate."),
        (r"\bDELETE\s+FROM\s+\w+\s*;", "high", "SQL-SEC-004", "DELETE without WHERE", "Verify intent and scope; use a transaction and backup/rollback plan."),
    ],
    "html": [
        (r"\bon[a-z]+\s*=\s*['\"]?javascript:", "high", "HTML-SEC-001", "Inline JavaScript URL", "Remove javascript: URLs and use safe event handling."),
        (r"<script\b[^>]*>\s*[^<]{0,200}\beval\s*\(", "high", "HTML-SEC-002", "Dynamic script evaluation", "Avoid eval and do not execute untrusted content."),
        (r"<iframe\b(?![^>]*\bsandbox\b)", "medium", "HTML-SEC-003", "Iframe without sandbox", "Add an appropriate sandbox attribute and narrowly allow required capabilities."),
        (r"<img\b(?![^>]*\balt\s*=)", "low", "HTML-A11Y-001", "Image missing alt attribute", "Add meaningful alternative text, or alt=\"\" for decorative images."),
    ],
}


def analyze_source(code: str, language: str) -> list[Finding]:
    if language == "python":
        return analyze_python(code)
    rules = LANGUAGE_RULES.get(language, [])
    findings: list[Finding] = []
    for pattern, severity, rule_id, title, recommendation in rules:
        for match in re.finditer(pattern, code, flags=re.IGNORECASE | re.MULTILINE):
            line = code.count("\n", 0, match.start()) + 1
            findings.append(Finding(
                rule_id=rule_id, severity=severity, title=title,
                message=f"A pattern associated with this risk was detected for {language}.",
                line=line, recommendation=recommendation,
            ))
    # Basic maintainability signals that apply across source formats.
    lines = code.splitlines()
    if len(lines) > 500:
        findings.append(Finding(
            rule_id=f"{language.upper()}-MAINT-001", severity="low",
            title="Large source file", message=f"The submitted file contains {len(lines)} lines.",
            line=1, recommendation="Consider separating cohesive responsibilities into smaller modules."
        ))
    return findings
