from app.services.analyzer import analyze_source


def rule_ids(code, language):
    return {finding.rule_id for finding in analyze_source(code, language)}


def test_javascript_eval_and_inner_html_are_flagged():
    ids = rule_ids("eval(userInput); element.innerHTML = userInput;", "javascript")
    assert {"JS-SEC-001", "JS-SEC-002"}.issubset(ids)


def test_typescript_any_is_flagged():
    assert "TS-QUAL-001" in rule_ids("function load(value: any) { return value; }", "typescript")


def test_java_runtime_exec_is_flagged():
    assert "JAVA-SEC-001" in rule_ids("Runtime.getRuntime().exec(command);", "java")


def test_php_unserialize_is_flagged():
    assert "PHP-SEC-003" in rule_ids("$data = unserialize($_POST['data']);", "php")


def test_sql_unscoped_update_is_flagged():
    assert "SQL-SEC-003" in rule_ids("UPDATE accounts SET active = 0;", "sql")


def test_html_missing_alt_is_flagged():
    assert "HTML-A11Y-001" in rule_ids('<img src="logo.png">', "html")


def test_python_dispatch_keeps_ast_rules():
    assert "PY-SEC-001" in rule_ids("eval(user_input)", "python")
