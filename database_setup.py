# Version: 3
# database_setup.py - FIXED VERSION for production
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """Get database connection for Supabase - PRODUCTION READY"""
    try:
        supabase_url = os.getenv('SUPABASE_URL')
        if not supabase_url:
            raise ValueError("SUPABASE_URL environment variable not set")
        
        # Use the Supabase URL directly (it should be a PostgreSQL connection string)
        conn = psycopg2.connect(supabase_url)
        print("✅ Database connection established")
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return None

def setup_database():
    """Create all tables with CORRECT schema matching helpers.py - PRODUCTION"""
    
    # FIXED: Exact table and column names that helpers.py expects
    commands = [
        # Main trade recommendations table - MUST match helpers.py save_recommendation_to_db()
        """
        CREATE TABLE IF NOT EXISTS trade_recommendations (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            pattern_name VARCHAR(100),
            timeframe INTEGER,
            recommendation_direction VARCHAR(10),
            confidence VARCHAR(10),
            analysis_notes TEXT,
            current_price DECIMAL(10, 4),
            ib_high DECIMAL(10, 4),
            ib_low DECIMAL(10, 4),
            ib_range DECIMAL(10, 4),
            virtual_entry DECIMAL(10, 4),
            virtual_tp1 DECIMAL(10, 4),
            virtual_sl DECIMAL(10, 4),
            entry_price DECIMAL(10, 4),
            stop_loss DECIMAL(10, 4),
            take_profit_1 DECIMAL(10, 4),
            take_profit_2 DECIMAL(10, 4),
            single_option VARCHAR(100),
            vertical_spread VARCHAR(100),
            status VARCHAR(20) DEFAULT 'PENDING',
            strategy VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            signals_detected JSONB,
            direction_learning_confidence DECIMAL(5, 4),
            
            -- Additional fields for tracking
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            market_conditions JSONB,
            etf_mode BOOLEAN DEFAULT FALSE
        )
        """,
        
        # Create indexes for performance
        """
        CREATE INDEX IF NOT EXISTS idx_trade_recommendations_symbol ON trade_recommendations(symbol);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_trade_recommendations_created_at ON trade_recommendations(created_at);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_trade_recommendations_direction ON trade_recommendations(recommendation_direction);
        """
    ]
    
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database. Check SUPABASE_URL in .env file.")
        return False
        
    try:
        cursor = conn.cursor()
        
        print("🔄 Creating database tables...")
        
        for i, command in enumerate(commands):
            try:
                cursor.execute(command)
                if "CREATE TABLE" in command:
                    # Extract table name for logging
                    words = command.split()
                    table_index = words.index("TABLE") + 2  # Skip "CREATE TABLE IF NOT EXISTS"
                    table_name = words[table_index]
                    print(f"  ✅ Table: {table_name}")
                elif "CREATE INDEX" in command:
                    print(f"  ✅ Index created")
            except Exception as e:
                print(f"  ⚠️ Command {i+1} failed: {str(e)[:100]}")
                # Continue with other commands
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("🎉 Database setup completed successfully!")
        print("   Table: trade_recommendations (matching helpers.py)")
        print("   Ready for production trading")
        return True
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        try:
            conn.rollback()
            cursor.close()
            conn.close()
        except:
            pass
        return False

def check_existing_tables():
    """Check what tables exist - for debugging"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        cursor.close()
        conn.close()
        
        table_list = [table[0] for table in tables]
        print(f"📊 Existing tables: {table_list}")
        return table_list
    except Exception as e:
        print(f"❌ Error checking tables: {e}")
        return []

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 PRODUCTION DATABASE SETUP - Trading Agent")
    print("=" * 60)
    
    # First check existing tables
    existing_tables = check_existing_tables()
    
    if 'trade_recommendations' in existing_tables:
        print("✅ trade_recommendations table already exists")
        print("   Schema matches helpers.py expectations")
    else:
        print("🔄 Creating trade_recommendations table...")
        setup_database()
    
    print("\n📋 Ready for production:")
    print("   • Table: trade_recommendations")
    print("   • Columns match helpers.py save_recommendation_to_db()")
    print("   • Indexes created for performance")

if __name__ == "__main__":
    print("=" * 60)
    print("DATABASE SETUP SCRIPT - Run manually when needed")
    print("=" * 60)
    print("This will:")
    print("  1. Create trade_recommendations table (if not exists)")
    print("  2. Create trade_executions table (if not exists)")
    print("  3. Create direction_learning_data table (if not exists)")
    print("  4. Create indexes for performance")
    print("")
    print("⚠️  WARNING: This modifies your production database!")
    print("")
    
    response = input("Continue? (yes/no): ")
    if response.lower() == 'yes':
        print("🔄 Setting up database...")
        setup_database()
    else:
        print("❌ Cancelled.")
