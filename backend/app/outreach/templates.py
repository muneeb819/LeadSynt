"""Outreach template library: deterministic rendering, seeding and lookup.

Rendering never fabricates. Known placeholder variables are filled from
verified ticket/contact/company data; anything unresolved renders as
``UNKNOWN`` (explicit, per project policy) and is reported in ``meta`` so
operators can fix the template.

Every rendered body gets the plain-language opt-out footer appended, which is
the compliance baseline for all automated outreach.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.outreach import FollowUpRule, OutreachTemplate

VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")

FOOTER = (
    "\n\n---\nYou are receiving this message because your company or profile was "
    "identified as a potential fit for the referenced requirement. Reply STOP or "
    "Unsubscribe to opt out of any further outreach."
)

# (name, channel, subject, body, description) — names double as the key the
# service uses to select a template by sequence: f"{channel}-sequence-{n}".
DEFAULT_TEMPLATES: list[tuple[str, str, str, str, str]] = [
    (
        "email-sequence-1", "email",
        "Quick note — {{reference}}",
        "Hi {{first_name}},\n\nWe recently learned that {{company_name}} may be "
        "looking for help with the requirements we saw referenced ({{reference}}). "
        "We'd love to arrange a short call to see whether we can help — would a "
        "brief call this week work for you?\n\nBest regards,\n{{sender_name}}",
        "First-touch outreach template (email, sequence 1)",
    ),
    (
        "email-sequence-2", "email",
        "Following up — {{reference}}",
        "Hi {{first_name}},\n\nQuick follow-up on the note I sent about "
        "{{reference}}. Happy to answer any questions or share more detail about "
        "how we could help {{company_name}}.\n\nBest regards,\n{{sender_name}}",
        "Follow-up #2 outreach template (email, sequence 2)",
    ),
    (
        "email-sequence-3", "email",
        "Last check — {{reference}}",
        "Hi {{first_name}},\n\nWanted to make sure you saw our earlier notes about "
        "{{reference}}. If now isn't the right time for {{company_name}}, just let "
        "us know and we won't follow up again.\n\nBest regards,\n{{sender_name}}",
        "Final follow-up outreach template (email, sequence 3)",
    ),
]

# (name, channel, sequence, delay_hours, max_follow_ups, requires_human_auth,
#  is_active, description)
DEFAULT_FOLLOW_UP_RULES: list[tuple[str, str, int, int, int, bool, bool, str]] = [
    (
        "email-followup", "email", 2, 48, 2, True, True,
        "Second message ~48h after the first; requires explicit human "
        "authorization after a reply/handover pause.",
    ),
    (
        "email-followup-final", "email", 3, 120, 1, True, True,
        "Final message ~5 days later; requires explicit human authorization "
        "after a reply/handover pause.",
    ),
]

# Fallback literal used when no seeded template matches a sequence — kept
# deterministic so the outreach agent and service always produce a draft.
FALLBACK_SUBJECT = "Quick note — {{reference}}"
FALLBACK_BODY = (
    "Hi {{first_name}},\n\nThanks for sharing your requirements referenced as "
    "{{reference}}. We would like to see whether we can help {{company_name}} — "
    "would a short call this week work for you?\n\nBest regards,\n{{sender_name}}"
)


def ensure_outreach_seeded(db: Session) -> None:
    """Idempotently seed the template library and follow-up rules (startup +
    tests). Only inserts missing rows; existing rows are left untouched."""
    existing = {t.name for t in db.execute(select(OutreachTemplate)).scalars()}
    for name, channel, subject, body, description in DEFAULT_TEMPLATES:
        if name not in existing:
            db.add(
                OutreachTemplate(
                    name=name, channel=channel, subject=subject, body=body,
                    description=description, is_active=True,
                )
            )
    rules = {(r.channel, r.sequence) for r in db.execute(select(FollowUpRule)).scalars()}
    for name, channel, sequence, delay, max_fu, needs_auth, active, desc in DEFAULT_FOLLOW_UP_RULES:
        if (channel, sequence) not in rules:
            db.add(
                FollowUpRule(
                    name=name, channel=channel, sequence=sequence,
                    delay_hours=delay, max_follow_ups=max_fu,
                    requires_human_authorization=needs_auth, is_active=active,
                    description=desc,
                )
            )
    db.flush()


def get_template(db: Session, name: str) -> OutreachTemplate | None:
    return db.execute(
        select(OutreachTemplate).where(OutreachTemplate.name == name)
    ).scalar_one_or_none()


def template_for_sequence(
    db: Session, channel: str, sequence: int
) -> OutreachTemplate | None:
    """The seeded template for a channel/sequence position, if any."""
    return get_template(db, f"{(channel or 'email').lower()}-sequence-{int(sequence)}")


def _context(contact, company, ticket, extra: dict[str, Any] | None) -> dict[str, Any]:
    s = get_settings()
    ctx: dict[str, Any] = {
        "first_name": (
            (contact.full_name or "").split()[0]
            if contact and contact.full_name
            else "there"
        ),
        "full_name": (contact.full_name if contact and contact.full_name else "there"),
        "company_name": (company.legal_name if company and company.legal_name else "your company"),
        "reference": (ticket.reference if ticket else "") or "",
        "sender_name": s.outreach_sender_name or "LeadSynt",
    }
    if extra:
        ctx.update({k: v for k, v in extra.items() if v is not None})
    return ctx


def _fill(text: str, ctx: dict[str, Any]) -> tuple[str, list[str]]:
    unresolved: list[str] = []

    def _sub(match: re.Match) -> str:
        key = match.group(1)
        value = ctx.get(key)
        if value not in (None, ""):
            return str(value)
        if key not in unresolved:
            unresolved.append(key)
        return "UNKNOWN"

    return VAR_RE.sub(_sub, text or ""), unresolved


def render_template(
    template: OutreachTemplate,
    *,
    contact=None,
    company=None,
    ticket=None,
    extra: dict[str, Any] | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """Render a stored template -> (subject, body_with_footer, meta)."""
    ctx = _context(contact, company, ticket, extra)
    subject, s_unresolved = _fill(template.subject, ctx)
    body, b_unresolved = _fill(template.body, ctx)
    unresolved = sorted(set(s_unresolved + b_unresolved))
    return subject.strip(), (body.strip() + FOOTER).strip(), {
        "template": template.name,
        "unresolved_vars": unresolved,
        "footer_appended": True,
    }


def render_message_draft(
    db: Session,
    *,
    channel: str,
    sequence: int,
    contact=None,
    company=None,
    ticket=None,
    extra: dict[str, Any] | None = None,
) -> tuple[str, str, dict[str, Any], OutreachTemplate | None]:
    """Render the draft for a channel/sequence, preferring the seeded template
    and falling back to the built-in draft (deterministic, no fabrication)."""
    template = template_for_sequence(db, channel, sequence)
    if template is not None:
        subject, body, meta = render_template(
            template, contact=contact, company=company, ticket=ticket, extra=extra
        )
        return subject, body, meta, template
    ctx = _context(contact, company, ticket, extra)
    subject, _ = _fill(FALLBACK_SUBJECT, ctx)
    body, b_unresolved = _fill(FALLBACK_BODY, ctx)
    unresolved = sorted(set(b_unresolved))
    meta = {
        "template": None,
        "unresolved_vars": unresolved,
        "footer_appended": True,
    }
    return subject.strip(), (body.strip() + FOOTER).strip(), meta, None