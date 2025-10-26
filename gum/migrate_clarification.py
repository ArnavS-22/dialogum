#!/usr/bin/env python3
"""
Migration script to create the clarification_analyses table.

This script creates the database table for storing clarification detection
results. Run this once to set up the schema.

Usage:
    python -m gum.migrate_clarification
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gum.models import init_db
from gum.clarification_models import ClarificationAnalysis


async def run_migration():
    """Create the clarification_analyses table."""
    print("Starting clarification detection table migration...")
    
    # Get database path (same as GUM uses)
    db_path = Path.home() / ".cache" / "gum" / "gum.db"
    db_dir = db_path.parent
    
    print(f"Database location: {db_path}")
    
    # Initialize database connection
    try:
        engine, Session = await init_db(
            db_path=db_path.name,
            db_directory=str(db_dir)
        )
        print("✓ Database connection established")
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        return False
    
    # Create tables (this will create clarification_analyses if it doesn't exist)
    try:
        from sqlalchemy import text as sql_text
        
        async with engine.begin() as conn:
            # Import Base from clarification_models to ensure table is registered
            from gum.clarification_models import Base as ClarificationBase
            
            # Create all tables defined in the metadata
            await conn.run_sync(ClarificationBase.metadata.create_all)
            
            print("✓ Tables created/verified")
            
            # Verify the table exists
            result = await conn.execute(
                sql_text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='clarification_analyses'"
                )
            )
            table_exists = result.fetchone() is not None
            
            if table_exists:
                print("✓ clarification_analyses table confirmed")
                
                # Check schema
                result = await conn.execute(
                    sql_text("PRAGMA table_info(clarification_analyses)")
                )
                columns = result.fetchall()
                print(f"✓ Table has {len(columns)} columns:")
                for col in columns:
                    print(f"  - {col[1]} ({col[2]})")
            else:
                print("✗ Table creation failed")
                return False
                
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await engine.dispose()
    
    print("\n✅ Migration completed successfully!")
    print("\nNext steps:")
    print("1. The clarification detection system is now ready")
    print("2. Enable it in config: clarification.enabled = True")
    print("3. Start in shadow mode: clarification.shadow_mode = True")
    print("4. New propositions will be automatically analyzed")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(run_migration())
    sys.exit(0 if success else 1)

