import os
import json
import time
import pytest
from pathlib import Path
from uuid import uuid4
from groq import Groq
from app.config import settings

pytestmark = pytest.mark.eval

@pytest.fixture
def golden_set():
    path = Path(__file__).parent / "eval" / "golden.json"
    return json.loads(path.read_text())

def test_full_rag_evaluation(client, db_session, golden_set):
    client.post("/api/v1/auth/signup", json={"email": "eval@test.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "eval@test.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    groq_client = Groq(api_key=settings.GROQ_API_KEY)
    scores = {"faithfulness": [], "answer_relevancy": [], "context_precision": [], "context_recall": []}

    print("\n--- Running RAG Evaluation (Groq Judge) ---")

    for i, entry in enumerate(golden_set):
        hub_res = client.post(
            "/api/v1/hubs",
            headers={**headers, "X-Idempotency-Key": str(uuid4())},
            json={"name": f"Hub {uuid4()}", "content": entry["hub_fixture"]},
        )
        hub_id = hub_res.json()["id"]
        query_res = client.post(
            f"/api/v1/hubs/{hub_id}/query",
            headers=headers,
            json={"question": entry["question"]},
        )
        data = query_res.json()
        generated_answer = data.get("answer", "")

        prompt = f"""You are an impartial evaluator. Grade the RAG system output.
[Question]: {entry['question']}
[Ground Truth]: {entry['expected_answer']}
[Retrieved Context]: {entry['hub_fixture']}
[Generated Answer]: {generated_answer}
Return ONLY a JSON object with integer values (1 for Yes, 0 for No) for faithfulness, answer_relevancy, context_precision, and context_recall."""

        try:
            chat = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=settings.GROQ_MODEL,
                temperature=0,
                response_format={"type": "json_object"}
            )
            grade = json.loads(chat.choices[0].message.content)
            for m in scores: scores[m].append(grade.get(m, 0))
            print(f"✓ [{i+1}/{len(golden_set)}] Faith: {grade.get('faithfulness')} | Rel: {grade.get('answer_relevancy')} | Prec: {grade.get('context_precision')} | Rec: {grade.get('context_recall')}")
        except Exception as e:
            print(f"✗ [{i+1}/{len(golden_set)}] Grading failed: {e}")
            for m in scores: scores[m].append(0)

        if i < len(golden_set) - 1:
                time.sleep(4)

    avg_faith = sum(scores["faithfulness"]) / len(scores["faithfulness"])
    avg_rel = sum(scores["answer_relevancy"]) / len(scores["answer_relevancy"])
    avg_prec = sum(scores["context_precision"]) / len(scores["context_precision"])
    avg_rec = sum(scores["context_recall"]) / len(scores["context_recall"])

    print(f"\n--- FINAL EVALUATION RESULTS ---")
    print(f"Faithfulness:      {avg_faith:.2f}")
    print(f"Answer Relevancy:  {avg_rel:.2f}")
    print(f"Context Precision: {avg_prec:.2f}")
    print(f"Context Recall:    {avg_rec:.2f}")

    assert avg_faith >= 0.70, f"Faithfulness ({avg_faith:.2f}) below threshold."
    assert avg_rel >= 0.70, f"Answer Relevancy ({avg_rel:.2f}) below threshold."