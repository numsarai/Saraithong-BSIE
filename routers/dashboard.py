"""
routers/dashboard.py
--------------------
Dashboard overview API — unified summary of the entire BSIE system.
"""

from services.auth_service import require_auth
from fastapi import Depends, APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from persistence.base import get_db_session
from persistence.models import (
    Account, Alert, FileRecord, ParserRun, Transaction,
)

router = APIRouter(prefix="/api", tags=["dashboard"], dependencies=[Depends(require_auth)])


@router.get("/dashboard")
async def api_dashboard():
    """Return unified dashboard data: counts, alerts, recent activity, top accounts."""
    with get_db_session() as session:
        # Record counts
        file_count = session.scalar(select(func.count(FileRecord.id))) or 0
        account_count = session.scalar(select(func.count(Account.id))) or 0
        txn_count = session.scalar(select(func.count(Transaction.id))) or 0
        run_count = session.scalar(select(func.count(ParserRun.id))) or 0

        # Transaction totals
        total_in = float(session.scalar(
            select(func.sum(func.abs(Transaction.amount)))
            .where(Transaction.direction == "IN")
        ) or 0)
        total_out = float(session.scalar(
            select(func.sum(func.abs(Transaction.amount)))
            .where(Transaction.direction == "OUT")
        ) or 0)

        # Alert summary
        alert_total = session.scalar(select(func.count(Alert.id))) or 0
        alert_new = session.scalar(
            select(func.count(Alert.id)).where(Alert.status == "new")
        ) or 0
        alert_critical = session.scalar(
            select(func.count(Alert.id)).where(Alert.severity == "critical")
        ) or 0
        alert_high = session.scalar(
            select(func.count(Alert.id)).where(Alert.severity == "high")
        ) or 0

        # Recent parser runs (last 5)
        recent_runs = session.scalars(
            select(ParserRun)
            .order_by(ParserRun.started_at.desc())
            .limit(5)
        ).all()
        recent_activity = [
            {
                "id": run.id,
                "file_id": run.file_id,
                "status": run.status,
                "bank": run.bank_detected or "",
                "started_at": str(run.started_at),
                "finished_at": str(run.finished_at) if run.finished_at else None,
                "summary": run.summary_json or {},
            }
            for run in recent_runs
        ]

        # Top 10 accounts by transaction count
        top_accounts_query = (
            select(
                Account.normalized_account_number,
                Account.account_holder_name,
                Account.bank_name,
                func.count(Transaction.id).label("txn_count"),
            )
            .join(Transaction, Transaction.account_id == Account.id, isouter=True)
            .group_by(Account.id)
            .order_by(func.count(Transaction.id).desc())
            .limit(10)
        )
        top_accounts = [
            {
                "account": row.normalized_account_number or "",
                "name": row.account_holder_name or "",
                "bank": row.bank_name or "",
                "txn_count": int(row.txn_count),
            }
            for row in session.execute(top_accounts_query).all()
        ]

    return JSONResponse({
        "counts": {
            "files": file_count,
            "accounts": account_count,
            "transactions": txn_count,
            "parser_runs": run_count,
        },
        "totals": {
            "total_in": round(total_in, 2),
            "total_out": round(total_out, 2),
            "circulation": round(total_in + total_out, 2),
        },
        "alerts": {
            "total": alert_total,
            "new": alert_new,
            "critical": alert_critical,
            "high": alert_high,
        },
        "recent_activity": recent_activity,
        "top_accounts": top_accounts,
    })
