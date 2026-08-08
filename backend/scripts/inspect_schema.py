#!/usr/bin/env python3
"""Inspect database schema for auth tables."""

from app.database.session import engine
from sqlalchemy import inspect

def main():
    insp = inspect(engine)

    print("=" * 80)
    print("DATABASE SCHEMA VALIDATION")
    print("=" * 80)

    # Check all tables
    tables = insp.get_table_names()
    print(f"\n✓ Total tables: {len(tables)}")

    auth_tables = [t for t in tables if t in ['users', 'oauth_accounts', 'refresh_tokens',
                                                'token_blacklist', 'email_verification_tokens',
                                                'logged_out_tokens', 'auth_audit_logs']]
    print(f"✓ Auth tables found: {len(auth_tables)}/{7}")
    for table in auth_tables:
        print(f"  - {table}")

    # Check users table in detail
    if 'users' in tables:
        print("\n" + "=" * 80)
        print("USERS TABLE SCHEMA")
        print("=" * 80)

        columns = insp.get_columns('users')
        print(f"\n✓ Columns ({len(columns)}):")
        for col in columns:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            print(f"  - {col['name']:<30} {str(col['type']):<20} {nullable}")

        # Check indexes
        indexes = insp.get_indexes('users')
        print(f"\n✓ Indexes ({len(indexes)}):")
        for idx in indexes:
            unique = "UNIQUE" if idx.get('unique') else ""
            cols = ', '.join(idx['column_names'])
            print(f"  - {idx['name']:<40} {unique:<10} ({cols})")

        # Check foreign keys
        fks = insp.get_foreign_keys('users')
        print(f"\n✓ Foreign Keys ({len(fks)}):")
        if fks:
            for fk in fks:
                print(f"  - {fk}")
        else:
            print("  - None (users table is parent)")

    # Check jobs table has user_id FK
    if 'jobs' in tables:
        print("\n" + "=" * 80)
        print("JOBS TABLE - USER RELATIONSHIP")
        print("=" * 80)

        columns = insp.get_columns('jobs')
        user_id_col = next((c for c in columns if c['name'] == 'user_id'), None)

        if user_id_col:
            print(f"\n✓ user_id column exists:")
            nullable = "NULL" if user_id_col['nullable'] else "NOT NULL"
            print(f"  - Type: {user_id_col['type']}")
            print(f"  - Nullable: {nullable}")
        else:
            print("\n✗ user_id column NOT FOUND")

        fks = insp.get_foreign_keys('jobs')
        user_fk = next((fk for fk in fks if 'user_id' in fk.get('constrained_columns', [])), None)

        if user_fk:
            print(f"\n✓ Foreign key to users:")
            print(f"  - References: {user_fk['referred_table']}.{user_fk['referred_columns']}")
            print(f"  - On delete: {user_fk.get('ondelete', 'NO ACTION')}")
        else:
            print("\n✗ Foreign key NOT FOUND")

    # Check critical auth tables
    critical_tables = ['email_verification_tokens', 'logged_out_tokens', 'refresh_tokens']
    for table in critical_tables:
        if table in tables:
            print(f"\n✓ {table} table exists")
            indexes = insp.get_indexes(table)
            if indexes:
                print(f"  Indexes: {', '.join(idx['name'] for idx in indexes)}")

if __name__ == "__main__":
    main()
