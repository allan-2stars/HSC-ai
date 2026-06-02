from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    create_student_and_login,
    register_parent,
)


# ── Test helpers ─────────────────────────────────────────────────────────────

def _make_taxonomy(client: TestClient, tokens: dict) -> tuple[str, str]:
    """Create a subject and exam type. Returns (subject_id, exam_type_id)."""
    subj = client.post(
        "/api/v1/admin/subjects",
        json={"code": "maths", "name": "Mathematics"},
        headers=auth_headers(tokens),
    ).json()
    et = client.post(
        "/api/v1/admin/exam-types",
        json={"code": "oc", "name": "Opportunity Class"},
        headers=auth_headers(tokens),
    ).json()
    return subj["id"], et["id"]


def _create_published_question(
    client: TestClient, tokens: dict, subject_id: str, exam_type_id: str, correct_answer: str = "A"
) -> dict:
    """Create and publish a question. Returns the question dict."""
    resp = client.post(
        "/api/v1/admin/questions",
        json={
            "subject_id": subject_id,
            "exam_type_id": exam_type_id,
            "year_level": 5,
            "difficulty": "medium",
            "question_type": "mcq",
            "source_type": "manual",
            "content_ownership": "original",
            "stem": f"What is 2 + 2? (answer: {correct_answer})",
            "correct_answer": correct_answer,
            "full_explanation": "2 + 2 = 4",
            "marks": 1,
            "options_json": [
                {"label": "A", "text": "4", "is_correct": correct_answer == "A", "explanation": ""},
                {"label": "B", "text": "3", "is_correct": correct_answer == "B", "explanation": ""},
                {"label": "C", "text": "5", "is_correct": correct_answer == "C", "explanation": ""},
                {"label": "D", "text": "6", "is_correct": correct_answer == "D", "explanation": ""},
            ],
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    question = resp.json()

    # Transition: draft → review → approved → published
    for status in ["review", "approved", "published"]:
        r = client.patch(
            f"/api/v1/admin/questions/{question['id']}/status",
            json={"status": status},
            headers=auth_headers(tokens),
        )
        assert r.status_code == 200, f"Failed to transition to {status}: {r.text}"

    # Re-fetch to get updated current_version
    r = client.get(
        f"/api/v1/admin/questions/{question['id']}",
        headers=auth_headers(tokens),
    )
    return r.json()


def _setup_published_exam(
    client: TestClient,
    tokens: dict,
    num_questions: int = 2,
) -> tuple[str, str, list[dict]]:
    """Full pipeline: create subject/exam_type, questions, template, sections, publish.
    Returns (template_id, instance_id, questions)."""
    sid, eid = _make_taxonomy(client, tokens)

    questions = []
    for i in range(num_questions):
        q = _create_published_question(
            client, tokens, sid, eid, correct_answer="A" if i % 2 == 0 else "B"
        )
        questions.append(q)

    # Create template
    resp = client.post(
        "/api/v1/admin/exam-templates",
        json={
            "title": "Test MCQ Exam",
            "exam_type_id": eid,
            "subject_id": sid,
            "year_level": 5,
            "duration_minutes": 30,
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    template = resp.json()

    # Create section
    resp = client.post(
        f"/api/v1/admin/exam-templates/{template['id']}/sections",
        json={"title": "Maths Section", "order_index": 0},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    section = resp.json()

    # Add questions to section
    for i, q in enumerate(questions):
        resp = client.post(
            f"/api/v1/admin/exam-templates/{template['id']}/sections/{section['id']}/questions",
            json={"question_id": q["id"], "order_index": i, "marks": 1},
            headers=auth_headers(tokens),
        )
        assert resp.status_code == 201, resp.text

    # Transition template: draft → review → approved → published
    for status in ["review", "approved", "published"]:
        r = client.patch(
            f"/api/v1/admin/exam-templates/{template['id']}/status",
            json={"status": status},
            headers=auth_headers(tokens),
        )
        assert r.status_code == 200, f"Failed to transition template to {status}: {r.text}"

    # Create instance
    resp = client.post(
        "/api/v1/admin/exam-instances",
        json={"template_id": template["id"], "title": "Test MCQ Exam Instance"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    instance = resp.json()

    # Publish instance
    resp = client.post(
        f"/api/v1/admin/exam-instances/{instance['id']}/publish",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200, resp.text
    instance = resp.json()

    return template["id"], instance["id"], questions


# ── Admin: ExamTemplate Tests ────────────────────────────────────────────────

def test_admin_can_create_exam_template(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    resp = client.post(
        "/api/v1/admin/exam-templates",
        json={
            "title": "Year 5 OC Maths",
            "exam_type_id": eid,
            "subject_id": sid,
            "year_level": 5,
            "duration_minutes": 30,
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Year 5 OC Maths"
    assert data["status"] == "draft"
    assert data["duration_minutes"] == 30
    assert data["year_level"] == 5


def test_non_admin_cannot_create_template(client: TestClient):
    tokens = register_parent(client)
    resp = client.post("/api/v1/admin/exam-templates", json={}, headers=auth_headers(tokens))
    assert resp.status_code == 403


def test_admin_can_create_exam_section(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    resp = client.post(
        "/api/v1/admin/exam-templates",
        json={"title": "Test", "exam_type_id": eid, "duration_minutes": 30},
        headers=auth_headers(tokens),
    )
    template_id = resp.json()["id"]

    resp = client.post(
        f"/api/v1/admin/exam-templates/{template_id}/sections",
        json={"title": "Section 1", "order_index": 0, "instructions": "Answer all questions"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Section 1"
    assert data["order_index"] == 0
    assert data["instructions"] == "Answer all questions"


def test_admin_can_add_published_question_to_section(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)
    question = _create_published_question(client, tokens, sid, eid)

    # Create template and section
    resp = client.post(
        "/api/v1/admin/exam-templates",
        json={"title": "Test", "exam_type_id": eid, "duration_minutes": 30},
        headers=auth_headers(tokens),
    )
    template_id = resp.json()["id"]
    resp = client.post(
        f"/api/v1/admin/exam-templates/{template_id}/sections",
        json={"title": "Section 1", "order_index": 0},
        headers=auth_headers(tokens),
    )
    section_id = resp.json()["id"]

    resp = client.post(
        f"/api/v1/admin/exam-templates/{template_id}/sections/{section_id}/questions",
        json={"question_id": question["id"], "order_index": 0, "marks": 2},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["question_id"] == question["id"]
    assert data["marks"] == 2


# ── Publish Validation Tests ─────────────────────────────────────────────────

def test_template_cannot_publish_with_no_sections(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    resp = client.post(
        "/api/v1/admin/exam-templates",
        json={"title": "Test", "exam_type_id": eid, "duration_minutes": 30},
        headers=auth_headers(tokens),
    )
    template_id = resp.json()["id"]

    # Try to go straight to published (should fail - no sections)
    for status in ["review", "approved"]:
        r = client.patch(
            f"/api/v1/admin/exam-templates/{template_id}/status",
            json={"status": status},
            headers=auth_headers(tokens),
        )
        assert r.status_code == 200, r.text

    r = client.patch(
        f"/api/v1/admin/exam-templates/{template_id}/status",
        json={"status": "published"},
        headers=auth_headers(tokens),
    )
    assert r.status_code == 409
    assert "no sections" in r.json()["detail"].lower()


def test_template_cannot_publish_with_no_questions_in_section(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    resp = client.post(
        "/api/v1/admin/exam-templates",
        json={"title": "Test", "exam_type_id": eid, "duration_minutes": 30},
        headers=auth_headers(tokens),
    )
    template_id = resp.json()["id"]

    client.post(
        f"/api/v1/admin/exam-templates/{template_id}/sections",
        json={"title": "Empty Section", "order_index": 0},
        headers=auth_headers(tokens),
    )

    # Transition to approved
    for status in ["review", "approved"]:
        r = client.patch(
            f"/api/v1/admin/exam-templates/{template_id}/status",
            json={"status": status},
            headers=auth_headers(tokens),
        )
        assert r.status_code == 200

    r = client.patch(
        f"/api/v1/admin/exam-templates/{template_id}/status",
        json={"status": "published"},
        headers=auth_headers(tokens),
    )
    assert r.status_code == 409
    assert "no questions" in r.json()["detail"].lower()


def test_template_cannot_publish_with_unpublished_question(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    # Create a question but don't publish it
    resp = client.post(
        "/api/v1/admin/questions",
        json={
            "subject_id": sid,
            "exam_type_id": eid,
            "year_level": 5,
            "difficulty": "medium",
            "question_type": "mcq",
            "source_type": "manual",
            "content_ownership": "original",
            "stem": "Draft question",
            "correct_answer": "A",
            "full_explanation": "Because.",
            "marks": 1,
            "options_json": [
                {"label": "A", "text": "Yes", "is_correct": True, "explanation": ""},
            ],
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    draft_question = resp.json()  # status = draft

    resp = client.post(
        "/api/v1/admin/exam-templates",
        json={"title": "Test", "exam_type_id": eid, "duration_minutes": 30},
        headers=auth_headers(tokens),
    )
    template_id = resp.json()["id"]
    resp = client.post(
        f"/api/v1/admin/exam-templates/{template_id}/sections",
        json={"title": "Section 1", "order_index": 0},
        headers=auth_headers(tokens),
    )
    section_id = resp.json()["id"]
    client.post(
        f"/api/v1/admin/exam-templates/{template_id}/sections/{section_id}/questions",
        json={"question_id": draft_question["id"]},
        headers=auth_headers(tokens),
    )

    for status in ["review", "approved"]:
        r = client.patch(
            f"/api/v1/admin/exam-templates/{template_id}/status",
            json={"status": status},
            headers=auth_headers(tokens),
        )
        assert r.status_code == 200

    r = client.patch(
        f"/api/v1/admin/exam-templates/{template_id}/status",
        json={"status": "published"},
        headers=auth_headers(tokens),
    )
    assert r.status_code == 409
    assert "not published" in r.json()["detail"].lower()


# ── ExamInstance: Freeze Behavior ────────────────────────────────────────────

def test_exam_instance_freezes_question_versions(client: TestClient):
    tokens = create_admin_and_login(client)
    template_id, instance_id, questions = _setup_published_exam(client, tokens, num_questions=1)

    resp = client.get(
        f"/api/v1/admin/exam-instances/{instance_id}",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    instance = resp.json()
    assert len(instance["instance_questions"]) == 1

    frozen = instance["instance_questions"][0]
    assert frozen["question_id"] == questions[0]["id"]
    assert frozen["question_version_id"] == questions[0]["current_version"]["id"]


def test_changing_question_after_freeze_does_not_alter_instance(client: TestClient):
    tokens = create_admin_and_login(client)
    template_id, instance_id, questions = _setup_published_exam(client, tokens, num_questions=1)

    # Get the frozen version ID
    resp = client.get(
        f"/api/v1/admin/exam-instances/{instance_id}",
        headers=auth_headers(tokens),
    )
    frozen_version_id = resp.json()["instance_questions"][0]["question_version_id"]

    # Now update the question (add a new version)
    resp = client.post(
        f"/api/v1/admin/questions/{questions[0]['id']}/versions",
        json={
            "stem": "Updated stem",
            "correct_answer": "C",
            "full_explanation": "Updated explanation",
            "marks": 1,
            "options_json": [
                {"label": "C", "text": "Updated", "is_correct": True, "explanation": ""},
            ],
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201
    new_version = resp.json()

    # The instance should still reference the old frozen version
    resp = client.get(
        f"/api/v1/admin/exam-instances/{instance_id}",
        headers=auth_headers(tokens),
    )
    instance = resp.json()
    assert instance["instance_questions"][0]["question_version_id"] == frozen_version_id
    assert instance["instance_questions"][0]["question_version_id"] != new_version["id"]


# ── Student: Available Exams ─────────────────────────────────────────────────

def test_student_can_list_available_exams(client: TestClient):
    tokens = create_admin_and_login(client)
    _setup_published_exam(client, tokens, num_questions=2)

    student_tokens = create_student_and_login(client)

    resp = client.get("/api/v1/exams/available", headers=auth_headers(student_tokens))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["title"] == "Test MCQ Exam Instance"
    assert data[0]["question_count"] == 2
    assert data[0]["total_marks"] == 2


def test_non_student_cannot_list_exams(client: TestClient):
    tokens = register_parent(client)
    resp = client.get("/api/v1/exams/available", headers=auth_headers(tokens))
    assert resp.status_code == 403


# ── Attempt Lifecycle ────────────────────────────────────────────────────────

def test_student_can_start_attempt(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=2)

    student_tokens = create_student_and_login(client)

    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["attempt_id"]
    assert data["total_questions"] == 2
    assert len(data["questions"]) == 2
    assert data["questions"][0]["stem"]
    assert data["questions"][0]["correct_answer"]
    assert data["questions"][0]["options_json"]
    assert data["expires_at"]


def test_student_can_save_answer(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=2)

    student_tokens = create_student_and_login(client)

    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    attempt = resp.json()

    # Save answer for first question
    eiq_id = attempt["questions"][0]["exam_instance_question_id"]
    resp = client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={"exam_instance_question_id": eiq_id, "selected_option": "A"},
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["selected_option"] == "A"
    assert data["is_correct"] is None  # Not scored yet


def test_student_can_update_answer_before_submit(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=2)

    student_tokens = create_student_and_login(client)

    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    attempt = resp.json()
    eiq_id = attempt["questions"][0]["exam_instance_question_id"]

    # First answer
    client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={"exam_instance_question_id": eiq_id, "selected_option": "A"},
        headers=auth_headers(student_tokens),
    )

    # Update answer
    resp = client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={"exam_instance_question_id": eiq_id, "selected_option": "B"},
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["selected_option"] == "B"


def test_student_can_submit_attempt(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=2)

    student_tokens = create_student_and_login(client)

    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    attempt = resp.json()

    # Answer both questions correctly (both have correct_answer = "A" and "B" respectively)
    for q in attempt["questions"]:
        client.patch(
            f"/api/v1/attempts/{attempt['attempt_id']}/answers",
            json={"exam_instance_question_id": q["exam_instance_question_id"], "selected_option": "A"},
            headers=auth_headers(student_tokens),
        )

    resp = client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/submit",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "submitted"
    assert data["total_questions"] == 2
    assert data["submitted_at"]


def test_score_calculation_is_correct(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, questions = _setup_published_exam(client, tokens, num_questions=2)

    student_tokens = create_student_and_login(client)

    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    attempt = resp.json()

    # Answer Q1 with correct answer "A", Q2 incorrectly (correct is "B")
    q1 = attempt["questions"][0]
    q2 = attempt["questions"][1]
    client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={"exam_instance_question_id": q1["exam_instance_question_id"], "selected_option": "A"},
        headers=auth_headers(student_tokens),
    )
    client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={"exam_instance_question_id": q2["exam_instance_question_id"], "selected_option": "C"},
        headers=auth_headers(student_tokens),
    )

    resp = client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/submit",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["correct_count"] == 1
    assert data["score_percent"] == 50.0
    assert data["score_raw"] == 1  # Only Q1 correct (1 mark)


def test_unanswered_questions_count_incorrect(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=2)

    student_tokens = create_student_and_login(client)

    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    attempt = resp.json()

    # Only answer Q1, leave Q2 unanswered
    q1 = attempt["questions"][0]
    client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={"exam_instance_question_id": q1["exam_instance_question_id"], "selected_option": "A"},
        headers=auth_headers(student_tokens),
    )

    resp = client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/submit",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["correct_count"] == 1  # Only Q1 answered correctly
    assert data["score_raw"] == 1


def test_late_submission_marks_expired(client: TestClient):
    tokens = create_admin_and_login(client)
    # Create an exam with very short duration
    sid, eid = _make_taxonomy(client, tokens)
    q = _create_published_question(client, tokens, sid, eid, correct_answer="A")

    resp = client.post(
        "/api/v1/admin/exam-templates",
        json={"title": "Quick Exam", "exam_type_id": eid, "duration_minutes": 1},
        headers=auth_headers(tokens),
    )
    template_id = resp.json()["id"]
    resp = client.post(
        f"/api/v1/admin/exam-templates/{template_id}/sections",
        json={"title": "S1", "order_index": 0},
        headers=auth_headers(tokens),
    )
    section_id = resp.json()["id"]
    client.post(
        f"/api/v1/admin/exam-templates/{template_id}/sections/{section_id}/questions",
        json={"question_id": q["id"]},
        headers=auth_headers(tokens),
    )
    for status in ["review", "approved", "published"]:
        client.patch(
            f"/api/v1/admin/exam-templates/{template_id}/status",
            json={"status": status},
            headers=auth_headers(tokens),
        )
    resp = client.post(
        "/api/v1/admin/exam-instances",
        json={"template_id": template_id, "title": "Quick Instance"},
        headers=auth_headers(tokens),
    )
    instance_id = resp.json()["id"]
    client.post(
        f"/api/v1/admin/exam-instances/{instance_id}/publish",
        headers=auth_headers(tokens),
    )

    student_tokens = create_student_and_login(client)

    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    attempt = resp.json()

    # Answer correctly
    q1 = attempt["questions"][0]
    client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={"exam_instance_question_id": q1["exam_instance_question_id"], "selected_option": "A"},
        headers=auth_headers(student_tokens),
    )

    # Submit normally (duration is 1 min, but server time is still valid)
    resp = client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/submit",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "submitted"


def test_cannot_edit_answers_after_submit(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    student_tokens = create_student_and_login(client)

    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    attempt = resp.json()
    eiq_id = attempt["questions"][0]["exam_instance_question_id"]

    client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={"exam_instance_question_id": eiq_id, "selected_option": "A"},
        headers=auth_headers(student_tokens),
    )

    client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/submit",
        headers=auth_headers(student_tokens),
    )

    resp = client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={"exam_instance_question_id": eiq_id, "selected_option": "B"},
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 409
    assert "not in progress" in resp.json()["detail"].lower()


def test_cannot_submit_twice(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    student_tokens = create_student_and_login(client)

    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    attempt = resp.json()
    eiq_id = attempt["questions"][0]["exam_instance_question_id"]

    client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={"exam_instance_question_id": eiq_id, "selected_option": "A"},
        headers=auth_headers(student_tokens),
    )

    resp = client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/submit",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200

    resp = client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/submit",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 409


def test_cannot_access_another_student_attempt(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student1 = create_student_and_login(client, parent_tokens, display_name="Student One")
    student2 = create_student_and_login(client, parent_tokens, display_name="Student Two")

    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student1),
    )
    attempt_id = resp.json()["attempt_id"]

    resp = client.get(
        f"/api/v1/attempts/{attempt_id}",
        headers=auth_headers(student2),
    )
    assert resp.status_code == 403


def test_parent_cannot_submit_attempt(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    parent_tokens = register_parent(client)
    student_tokens = create_student_and_login(client, parent_tokens)

    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    attempt_id = resp.json()["attempt_id"]

    resp = client.post(
        f"/api/v1/attempts/{attempt_id}/submit",
        headers=auth_headers(parent_tokens),
    )
    assert resp.status_code == 403


def test_admin_cannot_submit_attempt(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    student_tokens = create_student_and_login(client)

    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    attempt_id = resp.json()["attempt_id"]

    resp = client.post(
        f"/api/v1/attempts/{attempt_id}/submit",
        headers=auth_headers(tokens),  # admin tokens
    )
    assert resp.status_code == 403


def test_attempt_result_after_submit(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=2)

    student_tokens = create_student_and_login(client)

    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    attempt = resp.json()

    q1 = attempt["questions"][0]
    q2 = attempt["questions"][1]
    client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={"exam_instance_question_id": q1["exam_instance_question_id"], "selected_option": "A"},
        headers=auth_headers(student_tokens),
    )
    client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={"exam_instance_question_id": q2["exam_instance_question_id"], "selected_option": "C"},
        headers=auth_headers(student_tokens),
    )

    client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/submit",
        headers=auth_headers(student_tokens),
    )

    resp = client.get(
        f"/api/v1/attempts/{attempt['attempt_id']}/result",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["score_percent"] == 50.0
    assert len(data["questions"]) == 2
    # Q1 should be correct
    assert data["questions"][0]["is_correct"] is True
    # Q2 should be incorrect
    assert data["questions"][1]["is_correct"] is False
    # Answers should have full question data for review
    assert data["questions"][0]["correct_answer"]
    assert data["questions"][0]["full_explanation"]


def test_audit_logs_created(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    student_tokens = create_student_and_login(client)

    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    attempt = resp.json()
    q = attempt["questions"][0]
    client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={"exam_instance_question_id": q["exam_instance_question_id"], "selected_option": "A"},
        headers=auth_headers(student_tokens),
    )
    client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/submit",
        headers=auth_headers(student_tokens),
    )

    # Check audit logs via admin API (there's no direct audit log API, so check the DB)
    import asyncio
    from tests.conftest import _SessionFactory

    async def _check():
        async with _SessionFactory() as session:
            from sqlalchemy import select as sa_select
            from app.models.audit import AuditLog
            result = await session.execute(
                sa_select(AuditLog).where(
                    AuditLog.action.in_([
                        "attempt_started", "answer_saved", "attempt_submitted",
                        "exam_instance_published",
                    ])
                )
            )
            return list(result.scalars().all())

    logs = asyncio.run(_check())
    actions = {log.action for log in logs}
    assert "exam_instance_published" in actions
    assert "attempt_started" in actions
    assert "answer_saved" in actions
    assert "attempt_submitted" in actions


def test_list_student_attempts(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    student_tokens = create_student_and_login(client)

    resp = client.get("/api/v1/students/me/attempts", headers=auth_headers(student_tokens))
    assert resp.status_code == 200
    assert resp.json() == []

    # Start and submit an attempt
    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    attempt = resp.json()
    q = attempt["questions"][0]
    client.patch(
        f"/api/v1/attempts/{attempt['attempt_id']}/answers",
        json={"exam_instance_question_id": q["exam_instance_question_id"], "selected_option": "A"},
        headers=auth_headers(student_tokens),
    )
    client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/submit",
        headers=auth_headers(student_tokens),
    )

    resp = client.get("/api/v1/students/me/attempts", headers=auth_headers(student_tokens))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "submitted"
    assert data[0]["total_questions"] == 1


def test_cannot_get_result_before_submit(client: TestClient):
    tokens = create_admin_and_login(client)
    _, instance_id, _ = _setup_published_exam(client, tokens, num_questions=1)

    student_tokens = create_student_and_login(client)

    resp = client.post(
        f"/api/v1/exams/{instance_id}/attempts/start",
        headers=auth_headers(student_tokens),
    )
    attempt_id = resp.json()["attempt_id"]

    resp = client.get(
        f"/api/v1/attempts/{attempt_id}/result",
        headers=auth_headers(student_tokens),
    )
    assert resp.status_code == 409
