#!/usr/bin/env python3
"""E2E foundation check — exercises the RUNNING stack (API + DB + Redis).

Usage:  cd backend && .venv/bin/python ../tests/e2e/foundation_check.py
Expects: backend on :8000, migrated + seeded database, Redis up.
Exit code 0 = all checks passed.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  [{PASS if ok else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def req(method: str, path: str, token: str | None = None, body=None) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


def main() -> int:
    print("LeadSynt foundation E2E check\n")

    print("1. Health & infrastructure")
    st, h = req("GET", "/api/v1/health")
    check("GET /api/v1/health -> 200", st == 200)
    check("database check ok", h.get("checks", {}).get("database") == "ok")
    check("redis check ok", h.get("checks", {}).get("redis") == "ok")
    st, r = req("GET", "/api/v1/health/ready")
    check("GET /api/v1/health/ready -> ready", st == 200 and r.get("status") == "ready")

    print("\n2. Authentication (JWT + RBAC)")
    st, login = req("POST", "/api/v1/auth/login", body={
        "email": "admin@leadsynt.io", "password": "LeadSynt-Dev-Only-2026",
    })
    check("admin login -> 200 + tokens", st == 200 and "access_token" in login)
    token = login.get("access_token", "")
    st, me = req("GET", "/api/v1/auth/me", token)
    check("GET /auth/me -> admin role", st == 200 and "admin" in me.get("roles", []))
    st, bad = req("POST", "/api/v1/auth/login", body={
        "email": "admin@leadsynt.io", "password": "wrong-password",
    })
    check("wrong password -> 401", st == 401)
    st, anon = req("GET", "/api/v1/tickets")
    check("unauthenticated /tickets -> 401", st == 401)

    # viewer cannot create
    st, vlogin = req("POST", "/api/v1/auth/login", body={
        "email": "viewer@leadsynt.io", "password": "LeadSynt-Dev-Only-2026",
    })
    vtoken = vlogin.get("access_token", "")
    st, denied = req("POST", "/api/v1/tickets", vtoken, body={"type_code": "GENERAL"})
    check("viewer cannot create ticket (RBAC 403)", st == 403)

    print("\n3. Ticket pipeline (real data)")
    st, tickets = req("GET", "/api/v1/tickets?page_size=5&sort=-lead_score", token)
    d = tickets.get("data", {})
    total = d.get("pagination", {}).get("total", 0)
    check("tickets exist (>= 10)", total >= 10, f"total={total}")
    first = (d.get("items") or [{}])[0]
    check("top ticket has lead score", isinstance(first.get("lead_score"), int))
    check("top ticket has provenance", bool(first.get("original_url") or first.get("platform")))

    st, t = req("POST", "/api/v1/tickets", token, body={
        "type_code": "RFP", "market_sector": "E2E-Check", "product": "E2E product",
        "requirement": "End-to-end foundation verification ticket.",
        "intent_level": "HIGH", "urgency": "WEEK", "budget": 1000, "currency": "USD",
        "company": {"legal_name": "E2E Co", "domain": "e2e-check.example.com"},
        "contact": {"full_name": "E2E Tester", "work_email": "e2e@e2e-check.example.com"},
        "original_url": "https://e2e.example.com/1",
    })
    check("POST /tickets -> 201", st == 201, f"ref={t.get('data', {}).get('reference')}")
    new_id = t.get("data", {}).get("id")
    check("new ticket scored on create", isinstance(t.get("data", {}).get("lead_score"), int))

    print("\n4. Status machine")
    st, bad = req("POST", f"/api/v1/tickets/{new_id}/status", token, body={"status": "WON"})
    check("illegal transition INGESTED->WON -> 409", st == 409)
    st, ok_t = req("POST", f"/api/v1/tickets/{new_id}/status", token, body={"status": "PROCESSING"})
    check("legal transition INGESTED->PROCESSING -> 200", st == 200)

    print("\n5. Verification")
    st, v = req("POST", "/api/v1/verification/email", token, body={
        "ticket_id": new_id, "email": "e2e@e2e-check.example.com",
    })
    check("valid email -> VERIFIED", st == 200 and v.get("data", {}).get("result") == "VERIFIED")
    st, v2 = req("POST", "/api/v1/verification/email", token, body={
        "ticket_id": new_id, "email": "spam@mailinator.com",
    })
    check("disposable email -> FAILED", st == 200 and v2.get("data", {}).get("result") == "FAILED")

    print("\n6. Duplicates")
    st, t2 = req("POST", "/api/v1/tickets", token, body={
        "type_code": "RFP", "product": "E2E product", "market_sector": "E2E-Check",
        "company": {"legal_name": "E2E Co", "domain": "e2e-check.example.com"},
        "contact": {"full_name": "E2E Tester", "work_email": "e2e@e2e-check.example.com"},
        "original_url": "https://e2e.example.com/2",
    })
    check("same email+domain -> DUPLICATE", t2.get("data", {}).get("duplicate_status") == "DUPLICATE")

    print("\n7. QA Master + agents + settings")
    st, q = req("POST", "/api/v1/qa/sweep", token)
    check("QA sweep -> 200 + summary", st == 200 and bool(q.get("data", {}).get("summary")))
    st, a = req("GET", "/api/v1/agents", token)
    check("12 agents registered", st == 200 and len(a.get("data", [])) == 12)
    st, s = req("GET", "/api/v1/settings", token)
    check("dynamic settings present", st == 200 and len(s.get("data", [])) >= 4)

    print("\n8. Audit trail")
    st, au = req("GET", "/api/v1/admin/audit?action=ticket.created&limit=5", token)
    check("audit logs recorded", st == 200 and len(au.get("data", [])) >= 2)

    print("\n9. Analytics")
    st, da = req("GET", "/api/v1/analytics/dashboard", token)
    kpis = da.get("data", {}).get("kpis", {})
    check("dashboard KPIs live", st == 200 and kpis.get("new_tickets_24h", 0) >= 10)

    failed = [r for r in results if not r[1]]
    print(f"\n{'=' * 50}")
    print(f"Result: {len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("Failed checks:")
        for name, _, detail in failed:
            print(f"  - {name} {detail}")
        return 1
    print("ALL FOUNDATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
