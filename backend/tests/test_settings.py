"""
Tests for settings dual-config (demo vs production).
"""
import os
import pytest

def test_default_env_is_demo(monkeypatch):
    """Default APP_ENV should be demo."""
    monkeypatch.setenv("APP_ENV", "demo")
    # Re-import to pick up env change
    import importlib, config.settings as s
    importlib.reload(s)
    assert s.Settings().is_demo is True

def test_production_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    import importlib, config.settings as s
    importlib.reload(s)
    assert s.Settings().is_production is True
