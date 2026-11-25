async def test_where_are_we():
    from app.db.session import engine
    import sqlalchemy as sa

    async with engine.connect() as conn:
        db = (
            await conn.execute(sa.text("SELECT current_database(), inet_server_addr()::text, version()"))
        ).one()
        print("\nCONNECTED TO:", tuple(db))
        tables = (
            await conn.execute(sa.text("SELECT count(*) FROM pg_tables WHERE schemaname='public'"))
        ).scalar()
        print("TABLES VISIBLE TO ASYNCPG:", tables)
    assert True
