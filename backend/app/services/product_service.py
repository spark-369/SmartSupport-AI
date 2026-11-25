"""Product CRUD with slug management."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """'Aurora Coffee Maker X100' -> 'aurora-coffee-maker-x100'."""
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug[:160] or "product"


async def _unique_slug(session: AsyncSession, base: str, exclude_id: uuid.UUID | None = None) -> str:
    candidate, suffix = base, 1
    while True:
        stmt = select(Product.id).where(Product.slug == candidate)
        existing = await session.scalar(stmt)
        if existing is None or (exclude_id is not None and existing == exclude_id):
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"[:160]


def _stats_select():
    """Aggregated document stats: total/per-status counts + chunk total."""
    return (
        func.count(Document.id).label("document_count"),
        func.count(Document.id)
        .filter(Document.status == DocumentStatus.PENDING)
        .label("pending_count"),
        func.count(Document.id)
        .filter(Document.status == DocumentStatus.PROCESSING)
        .label("processing_count"),
        func.count(Document.id)
        .filter(Document.status == DocumentStatus.READY)
        .label("ready_count"),
        func.count(Document.id)
        .filter(Document.status == DocumentStatus.FAILED)
        .label("failed_count"),
        func.coalesce(func.sum(Document.chunk_count), 0).label("total_chunks"),
    )


def _attach_stats(product: Product, row) -> Product:
    setattr(product, "document_count", int(row.document_count))
    setattr(product, "pending_count", int(row.pending_count))
    setattr(product, "processing_count", int(row.processing_count))
    setattr(product, "ready_count", int(row.ready_count))
    setattr(product, "failed_count", int(row.failed_count))
    setattr(product, "total_chunks", int(row.total_chunks or 0))
    return product


async def list_products(session: AsyncSession) -> list[Product]:
    """All products (newest first) with document stats — one grouped query."""
    stmt = (
        select(Product, *_stats_select())
        .outerjoin(Document, Document.product_id == Product.id)
        .group_by(Product.id)
        .order_by(Product.created_at.desc())
    )
    return [_attach_stats(row[0], row) for row in (await session.execute(stmt)).all()]


async def get_product(session: AsyncSession, product_id: uuid.UUID) -> Product | None:
    return await session.get(Product, product_id)


async def get_product_with_stats(session: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await get_product_or_404(session, product_id)
    stmt = select(*_stats_select()).where(Document.product_id == product.id)
    return _attach_stats(product, (await session.execute(stmt)).one())


async def get_product_or_404(session: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await get_product(session, product_id)
    if product is None:
        raise NotFoundError("Product not found.")
    return product


async def create_product(session: AsyncSession, data: ProductCreate, created_by: uuid.UUID) -> Product:
    slug = await _unique_slug(session, data.slug or slugify(data.name))
    product = Product(
        name=data.name.strip(),
        slug=slug,
        description=data.description,
        version=data.version,
        created_by=created_by,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    setattr(product, "document_count", 0)
    return product


async def update_product(session: AsyncSession, product: Product, data: ProductUpdate) -> Product:
    if data.slug is not None and data.slug != product.slug:
        product.slug = await _unique_slug(session, data.slug, exclude_id=product.id)
    if data.name is not None:
        new_name = data.name.strip()
        if new_name != product.name:
            product.name = new_name
            # Keep the denormalized snapshot on conversations in sync.
            await session.execute(
                update(Conversation)
                .where(Conversation.product_id == product.id)
                .values(product_name=product.name)
            )
    if data.description is not None:
        product.description = data.description
    if data.version is not None:
        product.version = data.version
    if data.is_active is not None:
        product.is_active = data.is_active
    await session.commit()
    await session.refresh(product)
    return product


async def delete_product(session: AsyncSession, product: Product) -> None:
    from app.services.retrieval import invalidate_product_index

    await session.delete(product)
    await session.commit()
    await invalidate_product_index(product.id)
