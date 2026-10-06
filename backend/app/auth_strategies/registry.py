from app.auth_strategies.api_key_header import ApiKeyHeaderAuthStrategy
from app.auth_strategies.base import AuthStrategy
from app.auth_strategies.basic import BasicAuthStrategy
from app.auth_strategies.bearer import BearerAuthStrategy
from app.auth_strategies.none import NoneAuthStrategy


class AuthStrategyRegistry:
    """Registry of available authentication strategies."""

    def __init__(self) -> None:
        self._strategies: dict[str, AuthStrategy] = {}

    def register(self, strategy: AuthStrategy) -> None:
        self._strategies[strategy.auth_method_id] = strategy

    def get(self, auth_method_id: str) -> AuthStrategy | None:
        return self._strategies.get(auth_method_id)

    def list_ids(self) -> list[str]:
        return sorted(self._strategies.keys())


auth_strategy_registry = AuthStrategyRegistry()


def register_default_auth_strategies() -> None:
    for strategy in (
        NoneAuthStrategy(),
        BasicAuthStrategy(),
        BearerAuthStrategy(),
        ApiKeyHeaderAuthStrategy(),
    ):
        auth_strategy_registry.register(strategy)
