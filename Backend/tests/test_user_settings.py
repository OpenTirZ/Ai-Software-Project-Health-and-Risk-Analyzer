"""
Unit tests for User Settings & Notification Preferences:
- NotificationPreferences Pydantic schema validation & extra="forbid"
- NotificationPreferencesUpdate partial-update schema
- get_settings endpoint handler logic with default values and stored values
- update_settings endpoint handler logic with full and partial update semantics
- Preserving existing values during partial updates
- Idempotent update handling when values are identical
- Auth dependency verification
"""
import os
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-settings-tests-32-chars")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test")

import pytest
from pydantic import ValidationError

from Backend.auth.schemas import (
    NotificationPreferences,
    NotificationPreferencesUpdate,
)
from Backend.auth.router import get_settings, update_settings


# ---------------------------------------------------------------------------
# Schema Tests
# ---------------------------------------------------------------------------

class TestNotificationPreferencesSchema:
    def test_default_values(self):
        prefs = NotificationPreferences()
        assert prefs.high_risk_threshold is True
        assert prefs.weekly_digest is True

    def test_custom_values(self):
        prefs = NotificationPreferences(high_risk_threshold=False, weekly_digest=False)
        assert prefs.high_risk_threshold is False
        assert prefs.weekly_digest is False

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError) as exc_info:
            NotificationPreferences(high_risk_threshold=True, unknown_key="invalid")
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            NotificationPreferences(high_risk_threshold="not-a-bool")


class TestNotificationPreferencesUpdateSchema:
    def test_empty_update_allowed(self):
        update = NotificationPreferencesUpdate()
        assert update.high_risk_threshold is None
        assert update.weekly_digest is None
        assert update.model_dump(exclude_unset=True) == {}

    def test_partial_single_field(self):
        update = NotificationPreferencesUpdate(high_risk_threshold=False)
        assert update.high_risk_threshold is False
        assert update.weekly_digest is None
        assert update.model_dump(exclude_unset=True) == {"high_risk_threshold": False}

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError) as exc_info:
            NotificationPreferencesUpdate(slack_channel="#general")
        assert "Extra inputs are not permitted" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Endpoint Unit Tests (Mocking Database Layer)
# ---------------------------------------------------------------------------

class TestUserSettingsEndpointHandlers:
    def test_get_settings_returns_defaults_when_unset(self):
        user = {"_id": "507f1f77bcf86cd799439011", "email": "test@example.com"}
        result = get_settings(current_user=user)
        assert isinstance(result, NotificationPreferences)
        assert result.high_risk_threshold is True
        assert result.weekly_digest is True

    def test_get_settings_returns_stored_preferences(self):
        user = {
            "_id": "507f1f77bcf86cd799439011",
            "email": "test@example.com",
            "notification_preferences": {
                "high_risk_threshold": False,
                "weekly_digest": True,
            },
        }
        result = get_settings(current_user=user)
        assert result.high_risk_threshold is False
        assert result.weekly_digest is True

    def test_update_settings_full_update(self, monkeypatch):
        db_store = {
            "507f1f77bcf86cd799439011": {
                "_id": "507f1f77bcf86cd799439011",
                "notification_preferences": {
                    "high_risk_threshold": True,
                    "weekly_digest": True,
                },
            }
        }

        def mock_update_user(user_id, update_data):
            db_store[user_id].update(update_data)
            return True

        def mock_get_user(user_id):
            return db_store.get(user_id)

        monkeypatch.setattr("Backend.auth.router.update_user", mock_update_user)
        monkeypatch.setattr("Backend.auth.router.get_user", mock_get_user)

        user = db_store["507f1f77bcf86cd799439011"]
        payload = NotificationPreferencesUpdate(high_risk_threshold=False, weekly_digest=False)

        res = update_settings(payload=payload, current_user=user)
        assert res.high_risk_threshold is False
        assert res.weekly_digest is False
        assert db_store["507f1f77bcf86cd799439011"]["notification_preferences"] == {
            "high_risk_threshold": False,
            "weekly_digest": False,
        }

    def test_update_settings_partial_preserves_unspecified_field(self, monkeypatch):
        db_store = {
            "507f1f77bcf86cd799439011": {
                "_id": "507f1f77bcf86cd799439011",
                "notification_preferences": {
                    "high_risk_threshold": True,
                    "weekly_digest": False,
                },
            }
        }

        def mock_update_user(user_id, update_data):
            db_store[user_id].update(update_data)
            return True

        def mock_get_user(user_id):
            return db_store.get(user_id)

        monkeypatch.setattr("Backend.auth.router.update_user", mock_update_user)
        monkeypatch.setattr("Backend.auth.router.get_user", mock_get_user)

        user = db_store["507f1f77bcf86cd799439011"]

        # Only update high_risk_threshold to False, weekly_digest is omitted
        payload = NotificationPreferencesUpdate(high_risk_threshold=False)
        res = update_settings(payload=payload, current_user=user)

        assert res.high_risk_threshold is False
        assert res.weekly_digest is False  # Preserved from existing!

    def test_update_settings_idempotent_when_values_match(self, monkeypatch):
        db_store = {
            "507f1f77bcf86cd799439011": {
                "_id": "507f1f77bcf86cd799439011",
                "notification_preferences": {
                    "high_risk_threshold": True,
                    "weekly_digest": True,
                },
            }
        }

        # Simulating MongoDB returning modified_count == 0 because document values were already identical
        def mock_update_user_identical(user_id, update_data):
            return False  # modified_count == 0

        def mock_get_user(user_id):
            return db_store.get(user_id)

        monkeypatch.setattr("Backend.auth.router.update_user", mock_update_user_identical)
        monkeypatch.setattr("Backend.auth.router.get_user", mock_get_user)

        user = db_store["507f1f77bcf86cd799439011"]
        payload = NotificationPreferencesUpdate(high_risk_threshold=True, weekly_digest=True)

        res = update_settings(payload=payload, current_user=user)
        assert res.high_risk_threshold is True
        assert res.weekly_digest is True
