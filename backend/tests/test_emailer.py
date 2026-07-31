"""E-posta katmanı testleri (ağa çıkmadan)."""

import requests

from app import emailer


def test_disabled_without_env(monkeypatch):
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    monkeypatch.delenv("EMAIL_FROM", raising=False)
    assert emailer.email_enabled() is False
    assert emailer.send_otp_email("a@b.edu.tr", "123456") is False


def test_sends_payload(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", "key-123")
    monkeypatch.setenv("EMAIL_FROM", "noreply@ornek.com")
    captured = {}

    class FakeResponse:
        status_code = 201

    def fake_post(url, json, headers, timeout):
        captured.update(url=url, json=json, headers=headers)
        return FakeResponse()

    monkeypatch.setattr(emailer.requests, "post", fake_post)

    assert emailer.send_otp_email("ali@uni.edu.tr", "654321") is True
    assert captured["url"] == emailer.BREVO_URL
    assert captured["headers"]["api-key"] == "key-123"
    assert captured["json"]["to"] == [{"email": "ali@uni.edu.tr"}]
    assert "654321" in captured["json"]["subject"]
    assert "654321" in captured["json"]["htmlContent"]


def test_network_error_returns_false(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", "key-123")
    monkeypatch.setenv("EMAIL_FROM", "noreply@ornek.com")

    def fake_post(*args, **kwargs):
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(emailer.requests, "post", fake_post)
    assert emailer.send_otp_email("ali@uni.edu.tr", "111111") is False
