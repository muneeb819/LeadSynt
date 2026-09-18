# LeadSynt — Reply Webhook

Inbound endpoint that receives replies from external messaging platforms and
triggers the **reply-handover rule** (see architecture/pipeline.md).

## Endpoint

`POST /api/v1/webhooks/reply` — **no JWT** (system-to-system); security comes
from the HMAC signature.

## Request

```json
{
  "platform": "email",
  "external_message_id": "ext-123",
  "ticket_reference": "TS-202609-0001",
  "from": "buyer@client.example.com",
  "to": "outreach@leadsynt.io",
  "subject": "Re: Our procurement requirement",
  "body": "Yes, we are still interested and can share the full scope today.",
  "sent_at": "2026-09-18T10:15:00Z"
}
```

## Signature (mandatory)

Headers:

- `X-LeadSynt-Signature: sha256=<hex hmac>` — HMAC-SHA256 of
  `"<timestamp>.<raw_body>"`
- `X-LeadSynt-Timestamp: <unix seconds>`

Secret: `LEADSynt_WEBHOOK_SHARED_SECRET` (backend env only; dev default
`change-me-webhook-secret` — change it).

Rules:
- missing/invalid signature → `401 invalid_webhook_signature`; a `webhook_events`
  row with `verification=FAILED` is stored (evidence kept, payload quarantined).
- timestamp older than 300 s → rejected (replay protection).
- successful verify → `webhook_events` row `SIGNED`, then processed.

## Processing (atomic per ticket)

1. Load ticket by reference (404 if unknown).
2. Store reply **verbatim** as a `conversation_message` (role=inbound).
3. Stop automated outreach for the ticket (`outreach.automation_paused` audit).
4. Keyword sentiment → status `REPLIED`; if positive and ticket was
   `OUTREACH_ACTIVE` → `HOT_LEAD`.
5. Create `handover_events` dossier + `HUMAN_HANDOVER` ticket event +
   notification to `ticket.owner_id`.
6. Return `200 { "data": { "handover_id": …, "status": "HOT_LEAD" } }`.

Idempotency: the same `external_message_id` received twice returns `200` with
`duplicate=true` and does not re-trigger handover.

## Test it live (dev)

```bash
python3 - <<'PY'
import hashlib, hmac, json, time, urllib.request
secret = b"change-me-webhook-secret"
body = json.dumps({"platform":"email","external_message_id":"e2e-1",
  "ticket_reference":"TS-202609-0001","from":"buyer@x.example.com",
  "to":"outreach@leadsynt.io","subject":"Re","body":"Interested.",
  "sent_at":"2026-09-18T10:00:00Z"}).encode()
ts = str(int(time.time()))
sig = hmac.new(secret, f"{ts}.".encode()+body, hashlib.sha256).hexdigest()
req = urllib.request.Request("http://127.0.0.1:8000/api/v1/webhooks/reply",
  data=body, method="POST",
  headers={"Content-Type":"application/json",
           "X-LeadSynt-Signature": f"sha256={sig}",
           "X-LeadSynt-Timestamp": ts})
print(urllib.request.urlopen(req).read().decode())
PY
```
