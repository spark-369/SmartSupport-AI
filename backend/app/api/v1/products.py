"""Product endpoints (admin-managed catalog)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.product import ProductCreate, ProductPublic, ProductUpdate
from app.services import product_service

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductPublic])
async def list_products(_: CurrentUser, db: DbSession) -> list[ProductPublic]:
    products = await product_service.list_products(db)
    return [ProductPublic.model_validate(p) for p in products]


@router.post("", response_model=ProductPublic, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    db: DbSession,
    admin: AdminUser,
) -> ProductPublic:
    product = await product_service.create_product(db, payload, created_by=admin.id)
    return ProductPublic.model_validate(product)


@router.get("/{product_id}", response_model=ProductPublic)
async def get_product(product_id: uuid.UUID, _: CurrentUser, db: DbSession) -> ProductPublic:
    product = await product_service.get_product_with_stats(db, product_id)
    return ProductPublic.model_validate(product)


@router.patch("/{product_id}", response_model=ProductPublic)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    db: DbSession,
    _: AdminUser,
) -> ProductPublic:
    product = await product_service.get_product_or_404(db, product_id)
    updated = await product_service.update_product(db, product, payload)
    return ProductPublic.model_validate(updated)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: uuid.UUID, db: DbSession, _: AdminUser) -> Response:
    product = await product_service.get_product_or_404(db, product_id)
    await product_service.delete_product(db, product)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
