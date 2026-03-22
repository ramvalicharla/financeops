from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Any, get_args, get_origin

import pytest
from pydantic import BaseModel

from financeops.modules.erp_sync.domain import canonical
from financeops.modules.erp_sync.domain.canonical.common import CanonicalDatasetBase


def _contains_float(annotation: Any) -> bool:
    if annotation is float:
        return True
    origin = get_origin(annotation)
    if origin is None:
        return False
    return any(_contains_float(arg) for arg in get_args(annotation))


def _iter_canonical_model_classes() -> Iterator[type[BaseModel]]:
    package = importlib.import_module("financeops.modules.erp_sync.domain.canonical")
    for module_info in pkgutil.iter_modules(package.__path__):  # type: ignore[attr-defined]
        if module_info.name.startswith("__"):
            continue
        module = importlib.import_module(f"{package.__name__}.{module_info.name}")
        for symbol in vars(module).values():
            if (
                isinstance(symbol, type)
                and issubclass(symbol, BaseModel)
                and symbol.__module__ == module.__name__
                and symbol.__name__.startswith("Canonical")
            ):
                yield symbol


def _build_min_payload(model_cls: type[BaseModel]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for name, field in model_cls.model_fields.items():
        required = field.is_required()
        if not required:
            continue
        if name == "dataset_token":
            payload[name] = "sha256:test-dataset-token"
            continue
        if name == "entity_id":
            payload[name] = "entity-001"
            continue
        if name == "currency":
            payload[name] = "INR"
            continue
        if name in {"from_date", "to_date", "as_at_date"}:
            payload[name] = date(2026, 1, 31)
            continue
        annotation = field.annotation
        origin = get_origin(annotation)
        if origin is list:
            payload[name] = []
        elif annotation is str:
            payload[name] = f"{name}-value"
        elif annotation is int:
            payload[name] = 0
        elif annotation is Decimal:
            payload[name] = Decimal("0")
        elif annotation is bool:
            payload[name] = False
        else:
            pytest.fail(f"Add sample payload rule for {model_cls.__name__}.{name}")
    return payload


def test_canonical_root_schemas_have_dataset_token_string() -> None:
    for root_name in canonical.__all__:
        model_cls = getattr(canonical, root_name)
        if not isinstance(model_cls, type) or not issubclass(model_cls, BaseModel):
            continue
        payload = _build_min_payload(model_cls)
        instance = model_cls(**payload)
        assert "dataset_token" in model_cls.model_fields
        assert isinstance(getattr(instance, "dataset_token"), str)


def test_canonical_monetary_annotations_do_not_use_float() -> None:
    for model_cls in _iter_canonical_model_classes():
        for field_name, field in model_cls.model_fields.items():
            assert not _contains_float(field.annotation), (
                f"{model_cls.__name__}.{field.alias or field_name} uses float annotation"
            )


def test_dataset_models_explicitly_declare_dataset_token() -> None:
    models = list(_iter_canonical_model_classes())
    dataset_models = [cls for cls in models if issubclass(cls, CanonicalDatasetBase)]
    assert dataset_models
    for model_cls in dataset_models:
        assert "dataset_token" in getattr(model_cls, "__annotations__", {}), (
            f"{model_cls.__name__} must declare dataset_token explicitly"
        )
