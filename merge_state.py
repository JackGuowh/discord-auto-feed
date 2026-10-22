"""合并两份 state.json（并发运行时避免冲突）：列表取并集，数字取最大值。"""
import json
import sys


def merge(a, b):
    out = dict(b)
    for k, v in a.items():
        if k not in out:
            out[k] = v
        elif isinstance(v, list) and isinstance(out[k], list):
            seen = set(out[k])
            out[k] = (out[k] + [x for x in v if x not in seen])[-800:]
        elif isinstance(v, (int, float)) and isinstance(out[k], (int, float)):
            out[k] = max(v, out[k])
        else:
            out[k] = v
    return out


if __name__ == "__main__":
    mine, target = sys.argv[1], sys.argv[2]
    a = json.load(open(mine, encoding="utf-8"))
    try:
        b = json.load(open(target, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        b = {}
    json.dump(merge(a, b), open(target, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
