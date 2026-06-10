#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aurix_demo_broker_execution.account import verify_demo_account


def main() -> int:
    demo_snapshot = {
        "account": {
            "login": 12345678,
            "server": "Exness-MT5Trial15",
            "name": "mk-demo",
            "company": "Exness Technologies Ltd",
            "currency": "GBP",
            "balance": 100.0,
            "equity": 100.0,
        }
    }
    realish_snapshot = {"account": {"server": "Exness-Real", "name": "main", "currency": "GBP"}}
    demo = verify_demo_account(demo_snapshot)
    realish = verify_demo_account(realish_snapshot)
    print(f"demo_account_verified: {demo['demo_account_verified']}")
    print(f"demo_account_reason: {demo['demo_account_reason']}")
    print(f"account_login_masked: {demo['account_login_masked']}")
    print(f"realish_account_verified: {realish['demo_account_verified']}")
    if not demo["demo_account_verified"]:
        print("FAIL: demo snapshot was not verified")
        return 1
    if realish["demo_account_verified"]:
        print("FAIL: real-looking snapshot was incorrectly verified as demo")
        return 1
    print("OK: demo account verification check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
