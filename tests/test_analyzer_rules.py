from app.services.analyzer import analyze_python

def test_eval_is_flagged():
    findings = analyze_python("result = eval(user_input)")
    assert any(f.rule_id == "PY-SEC-001" for f in findings)

def test_pickle_loads_is_flagged():
    findings = analyze_python("import pickle\nvalue = pickle.loads(data)")
    assert any(f.rule_id == "PY-SEC-004" for f in findings)

def test_yaml_load_is_flagged():
    findings = analyze_python("import yaml\nvalue = yaml.load(data)")
    assert any(f.rule_id == "PY-SEC-005" for f in findings)

def test_tls_verify_false_is_flagged():
    findings = analyze_python("requests.get(url, verify=False)")
    assert any(f.rule_id == "PY-SEC-006" for f in findings)
