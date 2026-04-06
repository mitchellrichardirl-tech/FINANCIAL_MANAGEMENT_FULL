
from src.statements.base import StatementConfig
from src.statements.configs import STATEMENT_CONFIGS


def test_from_dict_roundtrip_all_builtins():
    for cfg in STATEMENT_CONFIGS.values():
        assert StatementConfig.from_dict(cfg.to_dict()) == cfg

if __name__ == "__main__":
    test_from_dict_roundtrip_all_builtins()