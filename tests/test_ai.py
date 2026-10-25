import pytest
from unittest.mock import patch, MagicMock
from app.services.groq_service import hub_insights, answer_question, expand_query, AiUnavailable, _client

def test_hub_insights_success():
    with patch.object(_client.chat.completions, "create") as mock_create:
        mock_res = MagicMock()
        mock_res.choices = [MagicMock()]
        mock_res.choices[0].message.content = '{"summary": "Test summary", "questions": ["Q1", "Q2"]}'
        mock_res.usage.prompt_tokens = 10
        mock_res.usage.completion_tokens = 20
        mock_create.return_value = mock_res

        (summary, questions), in_tok, out_tok = hub_insights("Test content")
        assert summary == "Test summary"
        assert questions == ["Q1", "Q2"]
        assert in_tok == 10
        assert out_tok == 20

def test_hub_insights_failure_returns_none():
    with patch.object(_client.chat.completions, "create", side_effect=Exception("API Down")):
        (summary, questions), in_tok, out_tok = hub_insights("Test content")
        assert summary is None
        assert questions == []

def test_answer_question_verifies_evidence():
    with patch.object(_client.chat.completions, "create") as mock_create:
        mock_res1 = MagicMock()
        mock_res1.choices = [MagicMock()]
        mock_res1.choices[0].message.content = '{"answer": "20 days", "evidence": "20 days", "grounded": true}'
        mock_res1.usage.prompt_tokens = 10
        mock_res1.usage.completion_tokens = 20
        mock_create.return_value = mock_res1

        result, _, _ = answer_question("Employees get 20 days of leave.", "How many days?")
        assert result["grounded"] is True
        assert result["evidence"] == "20 days"

        mock_res2 = MagicMock()
        mock_res2.choices = [MagicMock()]
        mock_res2.choices[0].message.content = '{"answer": "20 days", "evidence": "40 days", "grounded": true}'
        mock_res2.usage.prompt_tokens = 10
        mock_res2.usage.completion_tokens = 20
        mock_create.return_value = mock_res2

        result, _, _ = answer_question("Employees get 20 days of leave.", "How many days?")
        assert result["grounded"] is False
        assert result["evidence"] is None

def test_expand_query_success():
    with patch.object(_client.chat.completions, "create") as mock_create:
        mock_res = MagicMock()
        mock_res.choices = [MagicMock()]
        mock_res.choices[0].message.content = '{"queries": ["alt1", "alt2"]}'
        mock_res.usage.prompt_tokens = 10
        mock_res.usage.completion_tokens = 20
        mock_create.return_value = mock_res

        alternatives, _, _ = expand_query("What is the policy?")
        assert alternatives == ["alt1", "alt2"]