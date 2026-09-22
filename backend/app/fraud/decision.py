"""Decision policy mapping a risk score to a transaction status."""

from app.core.config import settings
from app.schemas import TxnStatus


def decide(risk_score: int) -> TxnStatus:
    if risk_score >= settings.risk_threshold_block:
        return TxnStatus.REJECTED
    if risk_score >= settings.risk_threshold_review:
        return TxnStatus.FLAGGED
    return TxnStatus.APPROVED