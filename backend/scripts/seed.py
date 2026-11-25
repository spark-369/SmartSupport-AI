#!/usr/bin/env python3
"""Development seeding: admin user + demo product + sample manual (ingested inline).

Usage (from backend/):  python scripts/seed.py
"""
from __future__ import annotations

import asyncio
import shutil
import sys
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

SAMPLE_MANUAL = BASE_DIR.parent / "sample_data" / "aurora_coffee_maker_x100_manual.md"

from sqlalchemy import func, select  # noqa: E402

from app.core import cache  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionFactory  # noqa: E402
from app.models import Document, DocumentStatus, User  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.services.ingestion import run_ingestion  # noqa: E402
from app.services.product_service import slugify  # noqa: E402


async def seed() -> None:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    async with SessionFactory() as session:
        # --- admin user -----------------------------------------------------
        admin = await session.scalar(select(User).where(User.email == settings.seed_admin_email.lower()))
        if admin is None:
            admin = User(
                email=settings.seed_admin_email.lower(),
                hashed_password=hash_password(settings.seed_admin_password),
                full_name="Support Admin",
                role=UserRole.ADMIN,
            )
            session.add(admin)
            await session.commit()
            print(f"[seed] created admin {admin.email} (password from SEED_ADMIN_PASSWORD)")
        else:
            print(f"[seed] admin {admin.email} already exists")

        # --- demo product ---------------------------------------------------
        product = await session.scalar(select(Product).where(Product.slug == slugify("Aurora Coffee Maker X100")))
        if product is None:
            product = Product(
                name="Aurora Coffee Maker X100",
                slug=slugify("Aurora Coffee Maker X100"),
                description="18-bar espresso machine with milk steamer (demo product).",
                version="2.1",
                created_by=admin.id,
            )
            session.add(product)
            await session.commit()
            print(f"[seed] created product '{product.name}'")
        else:
            print(f"[seed] product '{product.name}' already exists")

        # --- sample manual document ------------------------------------------
        existing = await session.scalar(
            select(func.count()).select_from(Document).where(Document.product_id == product.id)
        )
        if existing:
            print(f"[seed] product already has {existing} document(s) — skipping manual copy")
            doc_id = None
        else:
            dest_dir = settings.upload_dir / str(product.id)
            dest_dir.mkdir(parents=True, exist_ok=True)
            stored_name = f"{uuid.uuid4().hex}.md"
            shutil.copy(SAMPLE_MANUAL, dest_dir / stored_name)
            document = Document(
                product_id=product.id,
                uploaded_by=admin.id,
                original_filename=SAMPLE_MANUAL.name,
                stored_path=f"{product.id}/{stored_name}",
                file_type=".md",
                size_bytes=(dest_dir / stored_name).stat().st_size,
                status=DocumentStatus.PENDING,
            )
            session.add(document)
            await session.commit()
            doc_id = str(document.id)
            print(f"[seed] staged manual as document {doc_id}")

    if doc_id:
        chunks = run_ingestion(doc_id)
        print(f"[seed] ingested manual → {chunks} chunks ready for retrieval")


if __name__ == "__main__":
    cache.init_sync_redis(get_settings().redis_url)
    asyncio.run(seed())
