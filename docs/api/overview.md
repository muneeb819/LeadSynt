# LeadSynt API — Overview

Base: `http://<host>:8000/api/v1` · OpenAPI docs: `GET /docs` (49 paths)
· All responses are JSON. Auth: `Authorization: Bearer <JWT>`.

## Conventions

- **Pagination**: list endpoints accept `page`, `page_size` (max 100), `sort`
  (`-field` desc). High-volume endpoints are designed for cursor pagination
  (`cursor` + `next_cursor` in the envelope when present).
  Envelope: `{ "data": [...], "pagination": { total, page, page_size, pages } }`.
- **Errors**: `4xx/5xx` →
  `{ "error": { "code": "machine_code", "message": "human text", "details": {...}, "request_id": "..." } }`
- **Request IDs**: every request gets an `X-Request-ID` (generated if absent),
  echoed back, recorded in `request_logs`, referenced by error responses and audit rows.
- **Status codes**: 200 ok · 201 created · 400 invalid input/transition to same ·
  401 unauthenticated · 403 permission or policy (e.g. `suppressed_contact`) ·
  404 missing · 409 conflict (e.g. `invalid_status_transition`, `duplicate_email`) ·
  422 schema violation · 429 rate limited (with `Retry-After`) · 500/503 infra.
- **Audit**: mutating operations write `audit_logs` rows (actor, action,
  before/after, request id) — queryable at `/admin/audit`.

## Endpoint catalog (49)

### Auth & identity
| Method & path | Notes |
|---|---|
| POST /auth/login | email+password → access (60m) + refresh (7d) tokens |
| POST /auth/refresh | rotate refresh token |
| GET /auth/me | current user + roles |

### Users & RBAC (admin)
| POST /users · GET /users · PATCH /users/{id} | create (role required), list, deactivate/assign |
| GET /admin/audit?action=&entity_type=&user_id=&limit= | audit trail query |

### Tickets (central object)
| POST /tickets · GET /tickets · GET /tickets/{id} | create scores on write; detail includes provenance, contacts, companies, verification history |
| PATCH /tickets/{id} · POST /tickets/{id}/status | guarded by transition map |
| POST /tickets/{id}/score | re-run lead-scoring agent, new snapshot |
| GET /tickets/{id}/scores | immutable history |

### Leads
| GET /leads | qualified tickets as leads (score ≥ threshold, default 60) |

### Contacts / Companies
| POST/GET /contacts · GET /contacts/{id} | consent + suppression fields |
| POST/GET /companies · GET /companies/{id} | domain mapping |

### Sources & connectors
| GET /sources · GET /sources/{key} | source item feed + connector registry |
| POST /sources/{key}/run | in-process connector run (returns run summary) |

### Verification
| POST /verification/email · POST /verification/domain | appends `verification_histories` rows |

### Scoring
| POST /tickets/{id}/score · GET /tickets/{id}/scores | (see tickets) |

### Outreach
| POST /outreach/messages | **blocked 403 if contact suppressed** or ticket not outreach-eligible |
| GET /outreach/messages?ticket_id= | message log |

### Conversations & handover
| GET /conversations?ticket_id= · GET /conversations/{id} | thread incl. verbatim replies |
| POST /tickets/{id}/handover | build dossier + notify owner (permission `handover:create`) |

### Deals / Appointments / Tasks
| POST/GET /deals · POST/GET /appointments · POST/GET /tasks | CRM-lite for the foundation |

### Marketplace
| GET /marketplace/items · GET /marketplace/items/{id} | read surface for the foundation phase |

### Analytics
| GET /analytics/dashboard | KPIs: new/verified/qualified/hot/replies/deals/avg score |
| GET /analytics/pipeline | status distribution |
| GET /analytics/quality | data-quality signals for QA |

### Agents
| GET /agents · GET /agents/{id} · GET /agents/{id}/runs | registry + execution history (tokens, cost, errors) |

### QA Master
| GET /qa/findings · POST /qa/sweep · PATCH /qa/findings/{id} | sweep runs in-process; findings with evidence + actions |

### Notifications
| GET /notifications · PATCH /notifications/{id} | in-app notification log |

### Settings (dynamic)
| GET /settings · GET /settings/{key} · PUT /settings/{key} | admin edits JSON values; audited |

### Webhooks
| POST /webhooks/reply | signature-verified reply ingestion (see webhooks.md) |

### Health
| GET /health · GET /health/ready | status + db/redis checks |

## Rate limiting

Per-user sliding window in Redis (default 120 req/min; 10/min on
`/auth/login`). Excess → `429` with `Retry-After` and `rate_limited` code.
