"""Seed basic subscription plans if they don't already exist. No Stripe, no billing logic."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import BillingPeriod, PackageType, SubscriptionPlan

_PLANS = [
    {"code": "all_access_monthly",  "name": "All Access — Monthly",  "package_type": PackageType.all_access, "billing_period": BillingPeriod.monthly},
    {"code": "all_access_annual",   "name": "All Access — Annual",   "package_type": PackageType.all_access, "billing_period": BillingPeriod.annual},
    {"code": "oc_monthly",          "name": "OC Prep — Monthly",     "package_type": PackageType.exam_type,  "billing_period": BillingPeriod.monthly},
    {"code": "selective_monthly",   "name": "Selective Prep — Monthly", "package_type": PackageType.exam_type, "billing_period": BillingPeriod.monthly},
]


async def seed_plans(db: AsyncSession) -> None:
    for p in _PLANS:
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.code == p["code"])
        )
        if not result.scalar_one_or_none():
            db.add(SubscriptionPlan(**p))
    await db.commit()
