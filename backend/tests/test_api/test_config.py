import pytest
from src.api.app import create_app
from src.config import ConfigError

@pytest.fixture
def make_app(tmp_path, monkeypatch):
    """Build an app against a throwaway DB with optional env + override config."""

    def _make(env=None, overrides=None):
        for key in (
            "RECEIPT_MATCH_DATE_TOLERANCE_DAYS",
            "RECEIPT_MATCH_AMOUNT_TOLERANCE",
            "RECEIPT_AUTO_LINK_THRESHOLD",
        ):
            monkeypatch.delenv(key, raising=False)
        for key, value in (env or {}).items():
            monkeypatch.setenv(key, value)
        config = {"TESTING": True, "DATABASE_PATH": str(tmp_path / "cfg.db")}
        config.update(overrides or {})
        return create_app(config)

    return _make


class TestReceiptMatchConfigDefaults:
    def test_date_tolerance_default(self, make_app):
        app = make_app()
        assert app.config["RECEIPT_MATCH_DATE_TOLERANCE_DAYS"] == 5
        assert isinstance(app.config["RECEIPT_MATCH_DATE_TOLERANCE_DAYS"], int)

    def test_amount_tolerance_default(self, make_app):
        app = make_app()
        assert app.config["RECEIPT_MATCH_AMOUNT_TOLERANCE"] == pytest.approx(0.01)

    def test_auto_link_threshold_default(self, make_app):
        app = make_app()
        assert app.config["RECEIPT_AUTO_LINK_THRESHOLD"] == pytest.approx(0.98)


class TestReceiptMatchConfigEnvOverrides:
    def test_env_values_are_cast(self, make_app):
        app = make_app(
            env={
                "RECEIPT_MATCH_DATE_TOLERANCE_DAYS": "3",
                "RECEIPT_MATCH_AMOUNT_TOLERANCE": "0.5",
                "RECEIPT_AUTO_LINK_THRESHOLD": "0.9",
            }
        )
        assert app.config["RECEIPT_MATCH_DATE_TOLERANCE_DAYS"] == 3
        assert app.config["RECEIPT_MATCH_AMOUNT_TOLERANCE"] == pytest.approx(0.5)
        assert app.config["RECEIPT_AUTO_LINK_THRESHOLD"] == pytest.approx(0.9)

    def test_config_dict_override_wins_over_env(self, make_app):
        app = make_app(
            env={"RECEIPT_MATCH_DATE_TOLERANCE_DAYS": "3"},
            overrides={"RECEIPT_MATCH_DATE_TOLERANCE_DAYS": 9},
        )
        assert app.config["RECEIPT_MATCH_DATE_TOLERANCE_DAYS"] == 9

    def test_non_integer_env_days_rejected(self, make_app):
        with pytest.raises(ConfigError):
            make_app(env={"RECEIPT_MATCH_DATE_TOLERANCE_DAYS": "five"})


# class TestReceiptMatchConfigValidation:
#     @pytest.mark.parametrize("bad", [-1, 2.5, "5", None])
#     def test_invalid_date_tolerance_rejected(self, make_app, bad):
#         with pytest.raises(ValueError, match="RECEIPT_MATCH_DATE_TOLERANCE_DAYS"):
#             make_app(overrides={"RECEIPT_MATCH_DATE_TOLERANCE_DAYS": bad})

#     def test_zero_date_tolerance_allowed(self, make_app):
#         app = make_app(overrides={"RECEIPT_MATCH_DATE_TOLERANCE_DAYS": 0})
#         assert app.config["RECEIPT_MATCH_DATE_TOLERANCE_DAYS"] == 0

#     def test_negative_amount_tolerance_rejected(self, make_app):
#         with pytest.raises(ValueError, match="RECEIPT_MATCH_AMOUNT_TOLERANCE"):
#             make_app(overrides={"RECEIPT_MATCH_AMOUNT_TOLERANCE": -0.01})

#     @pytest.mark.parametrize("bad", [-0.1, 1.5])
#     def test_out_of_range_threshold_rejected(self, make_app, bad):
#         with pytest.raises(ValueError, match="RECEIPT_AUTO_LINK_THRESHOLD"):
#             make_app(overrides={"RECEIPT_AUTO_LINK_THRESHOLD": bad})

#     def test_threshold_disable_sentinel_allowed(self, make_app):
#         app = make_app(overrides={"RECEIPT_AUTO_LINK_THRESHOLD": 1.01})
#         assert app.config["RECEIPT_AUTO_LINK_THRESHOLD"] == pytest.approx(1.01)
