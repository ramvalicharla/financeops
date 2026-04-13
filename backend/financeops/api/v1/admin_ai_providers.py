from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from financeops.api.deps import get_current_user
from financeops.db.models.users import IamUser
from financeops.llm.provider_registry import ProviderSlot, ProviderStatus, provider_registry
from financeops.llm.fallback import FALLBACK_CHAINS
from financeops.services.platform_identity import require_platform_owner

router = APIRouter(prefix="/admin/ai/providers", tags=["admin_ai_providers"])

_seeded = False


def _seed_registry() -> None:
    global _seeded
    if _seeded:
        return
    for task_type, chain in FALLBACK_CHAINS.items():
        for priority, cfg in enumerate(chain, start=1):
            name = f"{task_type}:{cfg.provider}:{cfg.model_name}"
            if provider_registry.get(name) is not None:
                continue
            provider_registry.register(
                ProviderSlot(
                    name=name,
                    provider=cfg.provider,
                    model=cfg.model_name,
                    task_types=[task_type],
                    priority=priority,
                    max_tokens=1000,
                    status=ProviderStatus.ACTIVE,
                    sensitivity_allowed=cfg.provider == "ollama",
                    cost_per_1k_tokens=Decimal("0.003"),
                )
            )
    _seeded = True


def _serialize_slot(slot: ProviderSlot) -> dict:
    return {
        "name": slot.name,
        "provider": slot.provider,
        "model": slot.model,
        "base_url": slot.base_url,
        "task_types": slot.task_types,
        "max_tokens": slot.max_tokens,
        "priority": slot.priority,
        "status": slot.status.value,
        "sensitivity_allowed": slot.sensitivity_allowed,
        "cost_per_1k_tokens": str(slot.cost_per_1k_tokens),
    }


class UpdateProviderRequest(BaseModel):
    priority: int | None = None
    task_types: list[str] | None = None
    status: ProviderStatus | None = None


@router.get("")
async def list_provider_slots(
    current_user: IamUser = Depends(get_current_user),
) -> dict:
    require_platform_owner(current_user)
    _seed_registry()
    return {"providers": [_serialize_slot(slot) for slot in provider_registry.list_all()]}


@router.post("/{slot_name}/disable")
async def disable_provider_slot(
    slot_name: str,
    current_user: IamUser = Depends(get_current_user),
) -> dict:
    require_platform_owner(current_user)
    _seed_registry()
    if not provider_registry.disable(slot_name):
        raise HTTPException(status_code=404, detail="provider slot not found")
    slot = provider_registry.get(slot_name)
    if slot is None:
        raise HTTPException(status_code=404, detail="provider slot not found")
    return _serialize_slot(slot)


@router.post("/{slot_name}/enable")
async def enable_provider_slot(
    slot_name: str,
    current_user: IamUser = Depends(get_current_user),
) -> dict:
    require_platform_owner(current_user)
    _seed_registry()
    if not provider_registry.enable(slot_name):
        raise HTTPException(status_code=404, detail="provider slot not found")
    slot = provider_registry.get(slot_name)
    if slot is None:
        raise HTTPException(status_code=404, detail="provider slot not found")
    return _serialize_slot(slot)


@router.patch("/{slot_name}")
async def update_provider_slot(
    slot_name: str,
    body: UpdateProviderRequest,
    current_user: IamUser = Depends(get_current_user),
) -> dict:
    require_platform_owner(current_user)
    _seed_registry()
    slot = provider_registry.update(
        slot_name,
        priority=body.priority,
        task_types=body.task_types,
        status=body.status,
    )
    if slot is None:
        raise HTTPException(status_code=404, detail="provider slot not found")
    return _serialize_slot(slot)


__all__ = ["router"]
