from chengdu_edu_core.diff import compute_field_changes


def test_compute_field_changes_detects_scalar_change():
    old = {"enrollment_scope": "A", "quota": 100}
    new = {"enrollment_scope": "B", "quota": 100}
    changes = compute_field_changes(old, new, prefix="fields")
    assert len(changes) == 1
    assert changes[0].field_path == "fields.enrollment_scope"
    assert changes[0].old_value == "A"
    assert changes[0].new_value == "B"


def test_compute_field_changes_detects_list_change():
    old = {"requirements": ["户籍"]}
    new = {"requirements": ["户籍", "房产"]}
    changes = compute_field_changes(old, new, prefix="fields")
    assert any(c.field_path == "fields.requirements" for c in changes)
