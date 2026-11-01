"""Small, additive schema migration runner for existing MVP databases."""
from sqlalchemy import Column, Integer, MetaData, Table, select

metadata = MetaData()
versions = Table('schema_versions', metadata, Column('version', Integer, primary_key=True))


def migrate(engine, base, v2_tables):
    # Existing unversioned MVP databases are adopted without changing their rows.
    legacy = [table for table in base.metadata.sorted_tables if table.name not in v2_tables and table.name not in ('v2_jobs', 'v2_recommendations', 'v2_transcripts', 'event_registration_fields', 'event_registration_answers')]
    base.metadata.create_all(engine, tables=legacy)
    metadata.create_all(engine)
    with engine.begin() as connection:
        applied = set(connection.execute(select(versions.c.version)).scalars())
        if 1 not in applied:
            base.metadata.create_all(connection, tables=[base.metadata.tables[name] for name in v2_tables])
            connection.execute(versions.insert().values(version=1))
        if 2 not in applied:
            base.metadata.create_all(connection, tables=[base.metadata.tables[name] for name in ('v2_jobs', 'v2_recommendations', 'v2_transcripts', 'event_registration_fields', 'event_registration_answers')])
            connection.execute(versions.insert().values(version=2))

        if 3 not in applied:
            base.metadata.create_all(connection, tables=[base.metadata.tables[name] for name in ('event_registration_fields', 'event_registration_answers')])
            connection.execute(versions.insert().values(version=3))
