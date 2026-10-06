import hashlib
from datetime import UTC, datetime

from app.models import OAuthAccessToken
from sqlalchemy.orm import Session


class OAuthTokenRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create(self, token_record: OAuthAccessToken) -> OAuthAccessToken:
        self._db.add(token_record)
        self._db.flush()
        return token_record

    def get_by_hash(self, token_hash: str) -> OAuthAccessToken | None:
        return (
            self._db.query(OAuthAccessToken)
            .filter(OAuthAccessToken.token_hash == token_hash, OAuthAccessToken.revoked.is_(False))
            .first()
        )

    def list_for_simulation(self, simulation_id: str, *, limit: int = 50) -> list[OAuthAccessToken]:
        return (
            self._db.query(OAuthAccessToken)
            .filter(OAuthAccessToken.simulation_id == simulation_id)
            .order_by(OAuthAccessToken.issued_at.desc())
            .limit(limit)
            .all()
        )

    def revoke_expired(self, *, before: datetime | None = None) -> int:
        cutoff = before or datetime.now(UTC)
        expired = (
            self._db.query(OAuthAccessToken)
            .filter(OAuthAccessToken.expires_at < cutoff, OAuthAccessToken.revoked.is_(False))
            .all()
        )
        for record in expired:
            record.revoked = True
        if expired:
            self._db.flush()
        return len(expired)
