from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.modules.locations.models import CpCostCentre, CpLocation
from financeops.utils.gstin import extract_state_code, validate_gstin


class LocationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _limit(limit: int) -> int:
        return max(1, min(limit, 1000))

    async def _get_location_or_404(self, tenant_id: uuid.UUID, location_id: uuid.UUID) -> CpLocation:
        row = (
            await self._session.execute(
                select(CpLocation).where(
                    CpLocation.id == location_id,
                    CpLocation.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Location not found")
        return row

    async def _get_cost_centre_or_404(
        self,
        tenant_id: uuid.UUID,
        cost_centre_id: uuid.UUID,
    ) -> CpCostCentre:
        row = (
            await self._session.execute(
                select(CpCostCentre).where(
                    CpCostCentre.id == cost_centre_id,
                    CpCostCentre.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Cost centre not found")
        return row

    async def get_cost_centre(self, tenant_id: uuid.UUID, cost_centre_id: uuid.UUID) -> CpCostCentre:
        return await self._get_cost_centre_or_404(tenant_id, cost_centre_id)

    def _normalize_location_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        payload = dict(data)
        gstin = payload.get("gstin")
        if gstin is not None:
            gstin = str(gstin).strip().upper()
            if gstin and not validate_gstin(gstin):
                raise ValidationError("Invalid GSTIN")
            payload["gstin"] = gstin or None

        if payload.get("gstin") and not payload.get("state_code"):
            payload["state_code"] = extract_state_code(str(payload["gstin"]))
        return payload

    async def create_location(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: dict[str, Any],
    ) -> CpLocation:
        payload = self._normalize_location_payload(data)
        existing = (
            await self._session.execute(
                select(CpLocation.id).where(
                    CpLocation.tenant_id == tenant_id,
                    CpLocation.entity_id == entity_id,
                    CpLocation.location_code == str(payload["location_code"]),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ValidationError("location_code already exists for entity")

        row = CpLocation(
            tenant_id=tenant_id,
            entity_id=entity_id,
            location_name=str(payload["location_name"]),
            location_code=str(payload["location_code"]),
            gstin=payload.get("gstin"),
            state_code=payload.get("state_code"),
            address_line1=payload.get("address_line1"),
            address_line2=payload.get("address_line2"),
            city=payload.get("city"),
            state=payload.get("state"),
            pincode=payload.get("pincode"),
            country_code=str(payload.get("country_code", "IND")).upper(),
            is_primary=bool(payload.get("is_primary", False)),
            is_active=bool(payload.get("is_active", True)),
        )
        self._session.add(row)
        await self._session.flush()

        if row.is_primary:
            row = await self.set_primary_location(tenant_id, entity_id, row.id)
        await self._session.refresh(row)
        return row

    async def update_location(
        self,
        tenant_id: uuid.UUID,
        location_id: uuid.UUID,
        data: dict[str, Any],
    ) -> CpLocation:
        row = await self._get_location_or_404(tenant_id, location_id)
        payload = self._normalize_location_payload(data)

        if "location_code" in payload and payload["location_code"] != row.location_code:
            dupe = (
                await self._session.execute(
                    select(CpLocation.id).where(
                        CpLocation.tenant_id == tenant_id,
                        CpLocation.entity_id == row.entity_id,
                        CpLocation.location_code == str(payload["location_code"]),
                        CpLocation.id != row.id,
                    )
                )
            ).scalar_one_or_none()
            if dupe is not None:
                raise ValidationError("location_code already exists for entity")

        for key, value in payload.items():
            if hasattr(row, key):
                setattr(row, key, value)
        await self._session.flush()
        if bool(payload.get("is_primary")):
            row = await self.set_primary_location(tenant_id, row.entity_id, row.id)
        await self._session.refresh(row)
        return row

    async def get_locations(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        skip: int,
        limit: int,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        bounded_limit = self._limit(limit)
        stmt = select(CpLocation).where(
            CpLocation.tenant_id == tenant_id,
            CpLocation.entity_id == entity_id,
        )
        if is_active is not None:
            stmt = stmt.where(CpLocation.is_active.is_(is_active))

        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(stmt.subquery())
                )
            ).scalar_one()
        )
        rows = (
            await self._session.execute(
                stmt.order_by(
                    CpLocation.is_primary.desc(),
                    CpLocation.location_name.asc(),
                )
                .offset(skip)
                .limit(bounded_limit)
            )
        ).scalars().all()
        return {
            "items": list(rows),
            "total": total,
            "skip": skip,
            "limit": bounded_limit,
            "has_more": (skip + len(rows)) < total,
        }

    async def get_location(self, tenant_id: uuid.UUID, location_id: uuid.UUID) -> CpLocation:
        return await self._get_location_or_404(tenant_id, location_id)

    async def set_primary_location(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> CpLocation:
        row = await self._get_location_or_404(tenant_id, location_id)
        if row.entity_id != entity_id:
            raise ValidationError("Location does not belong to entity")

        await self._session.execute(
            update(CpLocation)
            .where(
                CpLocation.tenant_id == tenant_id,
                CpLocation.entity_id == entity_id,
            )
            .values(is_primary=False)
        )
        row.is_primary = True
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def create_cost_centre(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        data: dict[str, Any],
    ) -> CpCostCentre:
        parent_id = data.get("parent_id")
        if parent_id is not None:
            parent = await self._get_cost_centre_or_404(tenant_id, uuid.UUID(str(parent_id)))
            if parent.entity_id != entity_id:
                raise ValidationError("Parent cost centre must belong to same entity")

        existing = (
            await self._session.execute(
                select(CpCostCentre.id).where(
                    CpCostCentre.tenant_id == tenant_id,
                    CpCostCentre.entity_id == entity_id,
                    CpCostCentre.cost_centre_code == str(data["cost_centre_code"]),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ValidationError("cost_centre_code already exists for entity")

        row = CpCostCentre(
            tenant_id=tenant_id,
            entity_id=entity_id,
            parent_id=uuid.UUID(str(parent_id)) if parent_id else None,
            cost_centre_code=str(data["cost_centre_code"]),
            cost_centre_name=str(data["cost_centre_name"]),
            description=data.get("description"),
            is_active=bool(data.get("is_active", True)),
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def update_cost_centre(
        self,
        tenant_id: uuid.UUID,
        cost_centre_id: uuid.UUID,
        data: dict[str, Any],
    ) -> CpCostCentre:
        row = await self._get_cost_centre_or_404(tenant_id, cost_centre_id)

        if "parent_id" in data and data["parent_id"] is not None:
            parent = await self._get_cost_centre_or_404(tenant_id, uuid.UUID(str(data["parent_id"])))
            if parent.entity_id != row.entity_id:
                raise ValidationError("Parent cost centre must belong to same entity")

        if "cost_centre_code" in data and data["cost_centre_code"] != row.cost_centre_code:
            dupe = (
                await self._session.execute(
                    select(CpCostCentre.id).where(
                        CpCostCentre.tenant_id == tenant_id,
                        CpCostCentre.entity_id == row.entity_id,
                        CpCostCentre.cost_centre_code == str(data["cost_centre_code"]),
                        CpCostCentre.id != row.id,
                    )
                )
            ).scalar_one_or_none()
            if dupe is not None:
                raise ValidationError("cost_centre_code already exists for entity")

        for key, value in data.items():
            if hasattr(row, key):
                setattr(row, key, value)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def get_cost_centres(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        skip: int,
        limit: int,
    ) -> dict[str, Any]:
        bounded_limit = self._limit(limit)
        stmt = select(CpCostCentre).where(
            CpCostCentre.tenant_id == tenant_id,
            CpCostCentre.entity_id == entity_id,
        )
        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(stmt.subquery())
                )
            ).scalar_one()
        )
        rows = (
            await self._session.execute(
                stmt.order_by(
                    CpCostCentre.cost_centre_name.asc(),
                    CpCostCentre.id.asc(),
                )
                .offset(skip)
                .limit(bounded_limit)
            )
        ).scalars().all()
        return {
            "items": list(rows),
            "total": total,
            "skip": skip,
            "limit": bounded_limit,
            "has_more": (skip + len(rows)) < total,
        }

    async def get_cost_centre_tree(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        rows = (
            await self._session.execute(
                select(CpCostCentre)
                .where(
                    CpCostCentre.tenant_id == tenant_id,
                    CpCostCentre.entity_id == entity_id,
                )
                .order_by(
                    CpCostCentre.cost_centre_name.asc(),
                    CpCostCentre.id.asc(),
                )
            )
        ).scalars().all()
        by_parent: dict[uuid.UUID | None, list[CpCostCentre]] = {}
        for row in rows:
            by_parent.setdefault(row.parent_id, []).append(row)

        def build(node: CpCostCentre) -> dict[str, Any]:
            return {
                "id": node.id,
                "tenant_id": node.tenant_id,
                "entity_id": node.entity_id,
                "parent_id": node.parent_id,
                "cost_centre_code": node.cost_centre_code,
                "cost_centre_name": node.cost_centre_name,
                "description": node.description,
                "is_active": node.is_active,
                "created_at": node.created_at,
                "updated_at": node.updated_at,
                "children": [build(child) for child in by_parent.get(node.id, [])],
            }

        roots = by_parent.get(None, [])
        return [build(root) for root in roots]


__all__ = ["LocationService"]
