from app.services.github_service import changed_line_numbers

def test_changed_line_numbers_maps_added_lines():
    patch = "@@ -1,2 +1,3 @@\n first\n+added\n second\n"
    assert changed_line_numbers(patch) == {2}

def test_changed_line_numbers_handles_new_file():
    patch = "@@ -0,0 +1,2 @@\n+line one\n+line two\n"
    assert changed_line_numbers(patch) == {1, 2}

def test_changed_line_numbers_empty_patch():
    assert changed_line_numbers(None) == set()
