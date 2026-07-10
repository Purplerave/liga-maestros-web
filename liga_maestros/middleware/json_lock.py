import os

def _lock_file(lock_fh):
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(lock_fh.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)


def _unlock_file(lock_fh):
    if os.name == "nt":
        import msvcrt
        lock_fh.seek(0)
        msvcrt.locking(lock_fh.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)


def update_json_list_by_id_locked(path, new_items):
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock_path = f"{path}.lock"
    with open(lock_path, "a+b") as lock_fh:
        _lock_file(lock_fh)
        try:
            merged = {}
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    for item in json.load(fh) or []:
                        item_id = str(item.get("id") or "").strip()
                        if item_id:
                            merged[item_id] = item
            except Exception:
                merged = {}
            for item in new_items:
                item_id = str(item.get("id") or "").strip()
                if item_id:
                    merged[item_id] = item
            tmp_path = f"{path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(list(merged.values()), fh, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        finally:
            _unlock_file(lock_fh)


def write_json_locked(path, payload):
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock_path = f"{path}.lock"
    with open(lock_path, "a+b") as lock_fh:
        _lock_file(lock_fh)
        try:
            tmp_path = f"{path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        finally:
            _unlock_file(lock_fh)


def update_json_object_locked(path, updates):
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock_path = f"{path}.lock"
    with open(lock_path, "a+b") as lock_fh:
        _lock_file(lock_fh)
        try:
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    current = json.load(fh)
            except Exception:
                current = {}
            if not isinstance(current, dict):
                current = {}
            current.update(updates or {})
            tmp_path = f"{path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(current, fh, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        finally:
            _unlock_file(lock_fh)


def append_jsonl_locked(path, payload):
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock_path = f"{path}.lock"
    with open(lock_path, "a+b") as lock_fh:
        _lock_file(lock_fh)
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        finally:
            _unlock_file(lock_fh)
