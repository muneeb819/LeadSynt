"""Duplicate detection tests (deterministic, explainable)."""


def test_exact_duplicate_email_and_domain(client, operator_headers):
    from app.tests.conftest import make_ticket_payload
    from app.services.dedup_service import check_duplicates
    from app.services.ticket_service import create_ticket
    from app.core.database import SessionLocal

    payload = make_ticket_payload()
    db = SessionLocal()
    try:
        t1 = create_ticket(db, data=payload, actor_type="test")
        db.commit()
        t2 = create_ticket(db, data=payload, actor_type="test")
        db.commit()
        assert t2.duplicate_status.value == "DUPLICATE"
        result = check_duplicates(db, t2)
        assert result.status.value == "DUPLICATE"
        assert result.matched_ticket_id == t1.id
    finally:
        db.close()


def test_possible_duplicate_email_only(client, operator_headers):
    from app.tests.conftest import make_ticket_payload
    from app.services.ticket_service import create_ticket
    from app.core.database import SessionLocal

    p1 = make_ticket_payload()
    p2 = make_ticket_payload(
        product="Solar panels",
        company={"legal_name": "Other Co", "domain": "other-co.example.com",
                 "website": "https://other-co.example.com"},
    )
    db = SessionLocal()
    try:
        t1 = create_ticket(db, data=p1, actor_type="test")
        db.commit()
        t2 = create_ticket(db, data=p2, actor_type="test")  # same contact email
        db.commit()
        assert t2.duplicate_status.value == "POSSIBLE_DUPLICATE"
    finally:
        db.close()


def test_unique_when_no_overlap(client, operator_headers):
    from app.tests.conftest import make_ticket_payload
    from app.services.ticket_service import create_ticket
    from app.core.database import SessionLocal

    p1 = make_ticket_payload()
    p2 = make_ticket_payload(
        product="Batteries",
        company={"legal_name": "Voltra", "domain": "voltra.example.com",
                 "website": "https://voltra.example.com"},
        contact={"full_name": "New Person", "work_email": "new.person@voltra.example.com"},
    )
    db = SessionLocal()
    try:
        create_ticket(db, data=p1, actor_type="test")
        db.commit()
        t2 = create_ticket(db, data=p2, actor_type="test")
        db.commit()
        assert t2.duplicate_status.value == "UNIQUE"
    finally:
        db.close()
