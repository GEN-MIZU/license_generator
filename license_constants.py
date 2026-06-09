"""
ライセンス署名用定数・ユーティリティ

Backend の app/core/license.py と同一の値・canonical JSON 規則を維持すること。
変更時は両方を同期すること。
"""
import json
from typing import Any

PRODUCT_NAME = "Smart Bed Control System"
ISSUED_BY = "Gen Mizushina d/b/a KOTOBUKI Digital Science Lab."


def canonical_json(data: dict[str, Any]) -> bytes:
    """signature を除いた dict を canonical JSON バイト列に変換する。"""
    payload = {k: v for k, v in data.items() if k != "signature"}
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
