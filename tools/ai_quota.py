"""Quota mensuel pour l'utilisation de la clé IA administrateur."""
from __future__ import annotations

from datetime import datetime

from Model import AiUsage, AppSetting, db


DEFAULT_MONTHLY_QUOTA = 20


def _positive_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def get_site_monthly_quota() -> int:
    return _positive_int(AppSetting.get('ai_site_monthly_quota'), DEFAULT_MONTHLY_QUOTA)


def get_user_monthly_quota(user_id: int) -> int:
    override = AppSetting.get(f'ai_site_monthly_quota_user_{user_id}')
    return _positive_int(override, get_site_monthly_quota()) if override is not None else get_site_monthly_quota()


def consume_site_quota(user_id: int) -> tuple[bool, int, int]:
    """Réserve un appel de la clé administrateur pour le mois courant."""
    period = datetime.utcnow().strftime('%Y-%m')
    quota = get_user_monthly_quota(user_id)
    usage = AiUsage.query.filter_by(user_id=user_id, period=period).first()
    if usage is None:
        usage = AiUsage(user_id=user_id, period=period, calls=0)
        db.session.add(usage)
    if usage.calls >= quota:
        return False, usage.calls, quota
    usage.calls += 1
    db.session.commit()
    return True, usage.calls, quota


def monthly_usage(user_id: int) -> tuple[int, int]:
    period = datetime.utcnow().strftime('%Y-%m')
    usage = AiUsage.query.filter_by(user_id=user_id, period=period).first()
    return (usage.calls if usage else 0), get_user_monthly_quota(user_id)
