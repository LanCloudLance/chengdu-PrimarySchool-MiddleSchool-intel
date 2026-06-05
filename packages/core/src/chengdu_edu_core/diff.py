import json

from chengdu_edu_core.models import FieldChange


def _serialize(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def compute_field_changes(old: dict, new: dict, prefix: str = "fields") -> list[FieldChange]:
    changes: list[FieldChange] = []
    all_keys = set(old.keys()) | set(new.keys())
    for key in sorted(all_keys):
        old_val = old.get(key)
        new_val = new.get(key)
        if _serialize(old_val) != _serialize(new_val):
            changes.append(
                FieldChange(
                    field_path=f"{prefix}.{key}",
                    old_value=_serialize(old_val) if old_val is not None else "",
                    new_value=_serialize(new_val) if new_val is not None else "",
                )
            )
    return changes
