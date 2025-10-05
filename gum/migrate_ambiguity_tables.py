#!/usr/bin/env python3
"""
Database migration script to add ambiguity analysis tables.
Run this to upgrade existing GUM databases with new schema.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text as sql_text
from gum.models import init_db, Base
from gum.ambiguity_models import AmbiguityAnalysis, UrgencyAssessment, ClarificationDialogue


async def migrate_database(db_path: str = None):
    """Add ambiguity analysis tables to existing GUM database.
    
    Args:
        db_path: Path to SQLite database. Defaults to ~/.cache/gum/gum.db
    """
    if db_path is None:
        db_path = os.path.expanduser("~/.cache/gum/gum.db")
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        print("Please run GUM first to create the database, or specify correct path.")
        return False
    
    print(f"🔄 Migrating database: {db_path}")
    print(f"   Adding ambiguity analysis tables...")
    
    try:
        # Initialize database connection
        engine, Session = await init_db(db_path)
        
        # Create new tables
        async with engine.begin() as conn:
            # Check if tables already exist
            result = await conn.execute(sql_text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ambiguity_analyses'"
            ))
            exists = result.fetchone()
            
            if exists:
                print("⚠️  Ambiguity tables already exist. Skipping creation.")
                print("   If you need to recreate them, manually drop the tables first:")
                print("   - ambiguity_analyses")
                print("   - urgency_assessments")
                print("   - clarification_dialogues")
                return True
            
            # Create all ambiguity-related tables
            await conn.run_sync(Base.metadata.create_all)
            print("✅ Successfully created tables:")
            print("   - ambiguity_analyses")
            print("   - urgency_assessments")
            print("   - clarification_dialogues")
        
        await engine.dispose()
        
        print("\n✅ Migration completed successfully!")
        print(f"   Database: {db_path}")
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def verify_migration(db_path: str = None):
    """Verify that migration was successful.
    
    Args:
        db_path: Path to SQLite database.
    """
    if db_path is None:
        db_path = os.path.expanduser("~/.cache/gum/gum.db")
    
    print(f"\n🔍 Verifying migration...")
    
    try:
        engine, Session = await init_db(db_path)
        
        async with engine.begin() as conn:
            # Check each table
            tables = [
                'ambiguity_analyses',
                'urgency_assessments',
                'clarification_dialogues'
            ]
            
            for table in tables:
                result = await conn.execute(sql_text(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
                ))
                if result.fetchone():
                    print(f"   ✓ {table}")
                else:
                    print(f"   ✗ {table} - MISSING!")
                    return False
            
            # Check for proper indexes
            result = await conn.execute(sql_text(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name LIKE '%ambiguity%' OR tbl_name LIKE '%urgency%' OR tbl_name LIKE '%clarification%'"
            ))
            indexes = result.fetchall()
            print(f"   ✓ Found {len(indexes)} indexes")
        
        await engine.dispose()
        print("\n✅ Migration verification passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Verification failed: {str(e)}")
        return False


async def main():
    """Main migration entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Migrate GUM database to add ambiguity analysis tables"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to GUM database (default: ~/.cache/gum/gum.db)"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify migration, don't perform it"
    )
    
    args = parser.parse_args()
    
    if args.verify_only:
        success = await verify_migration(args.db_path)
    else:
        success = await migrate_database(args.db_path)
        if success:
            await verify_migration(args.db_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
