import pytest
from unittest.mock import patch, MagicMock
from app.services.gemini import hub_insights, answer_question, AiUnavailable, _client

def test_hub_insights_success():
    with patch.object(_client.models, "generate_content") as mock_gen:
        mock_gen.return_value = MagicMock(text='{"summary": "Test summary", "questions": ["Q1", "Q2"]}')
        summary, questions = hub_insights("Test content")
        assert summary == "Test summary"
        assert questions == ["Q1", "Q2"]

def test_hub_insights_failure_returns_none():
    with patch.object(_client.models, "generate_content", side_effect=Exception("API Down")):
        summary, questions = hub_insights("Test content")
        assert summary is None
        assert questions == []

def test_answer_question_verifies_evidence():
    with patch.object(_client.models, "generate_content") as mock_gen:
        # Return evidence that IS in the text
        mock_gen.return_value = MagicMock(text='{"answer": "20 days", "evidence": "20 days", "grounded": true}')
        result = answer_question("Employees get 20 days of leave.", "How many days?")
        assert result["grounded"] is True
        assert result["evidence"] == "20 days"

        # Return evidence that is NOT in the text (hallucination)
        mock_gen.return_value = MagicMock(text='{"answer": "20 days", "evidence": "40 days", "grounded": true}')
        result = await_answer = answer_question("Employees get 20 days of leave.", "How many days?")
        assert result["grounded"] is False
        assert result["evidence"] is None