"""Inline developer calculator, conversions, and generator utilities for DevToolkit Spotlight."""

from __future__ import annotations

import math
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def evaluate_calc_query(query: str) -> List[Dict[str, Any]]:
    """Evaluate calculation or utility query and return structured result card."""
    raw = query.strip()
    if raw.startswith("="):
        raw = raw[1:].strip()

    if not raw:
        return [
            {
                "id": "calc_help",
                "title": "Calculator & Developer Utilities",
                "subtitle": "Type math expression, base conversion (0xFF in dec), '= uuid', or '= epoch'",
                "value": "",
                "type": "calc",
                "badge": "CALC",
                "action": "copy",
            }
        ]

    low = raw.lower()

    # 1. UUID / GUID generator
    if low in ("uuid", "guid", "uuidv4", "uuid()", "guid()"):
        generated_id = str(uuid.uuid4())
        return [
            {
                "id": "gen_uuid",
                "title": generated_id,
                "subtitle": "Random UUID v4 • Press Enter to copy to clipboard",
                "value": generated_id,
                "type": "calc",
                "badge": "UUID",
                "action": "copy",
            }
        ]

    # 2. Unix Epoch & Timestamp
    if low in ("now", "epoch", "time", "timestamp", "date"):
        now_ts = time.time()
        now_sec = int(now_ts)
        now_ms = int(now_ts * 1000)
        iso_str = datetime.now(timezone.utc).isoformat()
        return [
            {
                "id": "epoch_sec",
                "title": str(now_sec),
                "subtitle": f"Seconds Epoch • {iso_str} • Enter to copy",
                "value": str(now_sec),
                "type": "calc",
                "badge": "EPOCH",
                "action": "copy",
            },
            {
                "id": "epoch_ms",
                "title": str(now_ms),
                "subtitle": "Milliseconds Epoch • Enter to copy",
                "value": str(now_ms),
                "type": "calc",
                "badge": "EPOCH-MS",
                "action": "copy",
            },
            {
                "id": "iso_date",
                "title": iso_str,
                "subtitle": "ISO 8601 UTC Date String • Enter to copy",
                "value": iso_str,
                "type": "calc",
                "badge": "ISO",
                "action": "copy",
            },
        ]

    # Check if raw is a numeric epoch timestamp to convert to date
    if raw.isdigit() and len(raw) in (10, 13):
        ts = int(raw) / 1000.0 if len(raw) == 13 else int(raw)
        try:
            dt = datetime.fromtimestamp(ts)
            formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
            return [
                {
                    "id": "converted_epoch",
                    "title": formatted,
                    "subtitle": f"Epoch {raw} -> Local Time • Enter to copy",
                    "value": formatted,
                    "type": "calc",
                    "badge": "DATE",
                    "action": "copy",
                }
            ]
        except Exception:
            pass

    # 3. Base Conversions (Hex to Dec, Dec to Hex, Bin to Dec)
    # e.g. "0xff in dec" or "255 in hex" or "10 in bin"
    m_base = re.match(r"^(0x[0-9a-f]+|[0-9]+|0b[01]+)\s+(?:in|to)\s+(hex|dec|bin|oct)$", low)
    if m_base:
        val_str, target_base = m_base.group(1), m_base.group(2)
        try:
            num = int(val_str, 0)
            if target_base == "hex":
                res = hex(num).upper().replace("0X", "0x")
            elif target_base == "dec":
                res = str(num)
            elif target_base == "bin":
                res = bin(num)
            elif target_base == "oct":
                res = oct(num)
            else:
                res = str(num)
            return [
                {
                    "id": "base_conv",
                    "title": res,
                    "subtitle": f"{val_str} in {target_base} • Enter to copy",
                    "value": res,
                    "type": "calc",
                    "badge": "CONV",
                    "action": "copy",
                }
            ]
        except Exception:
            pass

    # Direct Hex or Bin inspection (e.g. "0xFF")
    if low.startswith("0x"):
        try:
            num = int(low, 16)
            return [
                {
                    "id": "hex_dec",
                    "title": str(num),
                    "subtitle": f"{raw} in Decimal • Enter to copy",
                    "value": str(num),
                    "type": "calc",
                    "badge": "DEC",
                    "action": "copy",
                }
            ]
        except Exception:
            pass

    # 4. Storage Unit Conversions (e.g. "16 gb in mb", "1024 mb in gb")
    m_unit = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*(kb|mb|gb|tb)\s+(?:in|to)\s+(kb|mb|gb|tb)$", low)
    if m_unit:
        val = float(m_unit.group(1))
        from_u = m_unit.group(2)
        to_u = m_unit.group(3)
        multipliers = {"kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4}
        bytes_val = val * multipliers[from_u]
        converted = bytes_val / multipliers[to_u]
        formatted = f"{converted:g} {to_u.upper()}"
        return [
            {
                "id": "unit_conv",
                "title": formatted,
                "subtitle": f"{val} {from_u.upper()} in {to_u.upper()} • Enter to copy",
                "value": formatted,
                "type": "calc",
                "badge": "UNIT",
                "action": "copy",
            }
        ]

    # 5. Math expression evaluation
    safe_namespace = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "math": math,
        "sqrt": math.sqrt,
        "pow": math.pow,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log2": math.log2,
        "log10": math.log10,
        "pi": math.pi,
        "e": math.e,
    }

    # Clean formula: replace ^ with **
    expr = raw.replace("^", "**")
    # Only allow safe mathematical characters
    if re.match(r"^[0-9+\-*/().,%*\s_a-zA-Z]+$", expr):
        try:
            result = eval(expr, {"__builtins__": {}}, safe_namespace)
            if isinstance(result, (int, float)):
                res_str = f"{result:g}" if isinstance(result, float) else str(result)
                return [
                    {
                        "id": "math_result",
                        "title": res_str,
                        "subtitle": f"= {raw} • Press Enter to copy to clipboard",
                        "value": res_str,
                        "type": "calc",
                        "badge": "CALC",
                        "action": "copy",
                    }
                ]
        except Exception:
            pass

    return [
        {
            "id": "calc_error",
            "title": f"Cannot evaluate: {raw}",
            "subtitle": "Check formula or syntax (e.g. 1024 * 16, 0xFF in dec, uuid, now)",
            "value": raw,
            "type": "calc",
            "badge": "ERROR",
            "action": "none",
        }
    ]

