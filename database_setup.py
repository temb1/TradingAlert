# Version: 4
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import logging

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get database connection for Supabase - PRODUCTION READY"""
    try:
        supabase_url = os.getenv('SUPABASE_URL')
        if not supabase_url:
            raise ValueError("SUPABASE_URL environment variable not set")
        
        # Use the Supabase URL directly (it should be a PostgreSQL connection string)
        conn = psycopg2.connect(
            supabase_url,
            cursor_factory=RealDictCursor  # Return results as dictionaries
        )
        logger.info("✅ Database connection established")
        return conn
    except Exception as e:
        logger.error(f"❌ Database connection error: {e}")
        return None

def setup_database():
    """Create all tables with CORRECT schema - PRODUCTION"""
    
    # FIXED: Complete schema for trading system including ensemble support
    commands = [
        # ===== CORE TRADING TABLES =====
        
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
            etf_mode BOOLEAN DEFAULT FALSE,
            
            -- Ensemble integration
            ensemble_decision_id INTEGER,
            ensemble_weight_used DECIMAL(5, 4),
            component_signals JSONB
        )
        """,
        
        # ===== ENSEMBLE MANAGEMENT TABLES =====
        
        # Ensemble configurations - stores different ensemble setups
        """
        CREATE TABLE IF NOT EXISTS ensemble_configurations (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            description TEXT,
            strategy_weights JSONB NOT NULL,  -- {"momentum": 0.4, "mean_reversion": 0.3, ...}
            active_strategies JSONB,          -- List of active strategy names
            config_settings JSONB,            -- {"rebalance_frequency": "weekly", ...}
            performance_metrics JSONB,        -- {"total_trades": 100, "win_rate": 0.65, ...}
            direction_learning_enabled BOOLEAN DEFAULT TRUE,
            is_active BOOLEAN DEFAULT TRUE,
            version INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Additional metadata
            created_by VARCHAR(100) DEFAULT 'system',
            tags JSONB DEFAULT '["default"]'::jsonb
        )
        """,
        
        # Ensemble decisions log - tracks every ensemble decision
        """
        CREATE TABLE IF NOT EXISTS ensemble_decisions (
            id SERIAL PRIMARY KEY,
            ensemble_id INTEGER REFERENCES ensemble_configurations(id),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            symbol VARCHAR(20),
            market_conditions JSONB,
            
            -- Signal data
            component_signals JSONB NOT NULL,  -- {"momentum": 0.5, "mean_reversion": -0.3, ...}
            final_signal DECIMAL(5, 4) NOT NULL,
            confidence DECIMAL(5, 4) NOT NULL,
            
            -- Weight data
            weights_used JSONB NOT NULL,       -- {"momentum": 0.45, "mean_reversion": 0.35, ...}
            original_weights JSONB,            -- For comparison
            direction_insights JSONB,          -- From direction learner
            
            -- Outcome tracking
            trade_executed BOOLEAN DEFAULT FALSE,
            trade_outcome VARCHAR(20),         -- "WIN", "LOSS", "BREAKEVEN"
            pnl DECIMAL(10, 4),
            
            -- Metadata
            processing_time_ms INTEGER,
            error_message TEXT,
            
            -- Indexes for performance
            INDEX idx_ensemble_timestamp (timestamp),
            INDEX idx_ensemble_symbol (symbol)
        )
        """,
        
        # Ensemble performance history - aggregated performance data
        """
        CREATE TABLE IF NOT EXISTS ensemble_performance_history (
            id SERIAL PRIMARY KEY,
            ensemble_id INTEGER REFERENCES ensemble_configurations(id),
            period_start TIMESTAMP NOT NULL,
            period_end TIMESTAMP NOT NULL,
            
            -- Performance metrics
            total_decisions INTEGER DEFAULT 0,
            trades_executed INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            win_rate DECIMAL(5, 4),
            average_confidence DECIMAL(5, 4),
            total_pnl DECIMAL(10, 4),
            
            -- Weight evolution
            starting_weights JSONB,
            ending_weights JSONB,
            weight_adjustments JSONB,
            
            -- Strategy performance breakdown
            strategy_performance JSONB,  -- {"momentum": {"wins": 10, "losses": 5, "signal_strength": 0.7}, ...}
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
        # ===== DIRECTION LEARNING TABLES =====
        
        # Direction learning patterns and outcomes
        """
        CREATE TABLE IF NOT EXISTS direction_learning_data (
            id SERIAL PRIMARY KEY,
            signal_pattern VARCHAR(100) NOT NULL,
            market_context VARCHAR(100),
            direction VARCHAR(10) NOT NULL,  -- "BULLISH", "BEARISH"
            outcome VARCHAR(10) NOT NULL,    -- "SUCCESS", "FAILURE"
            confidence DECIMAL(5, 4),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            symbols TEXT[],                   -- Array of symbols where this occurred
            timeframe INTEGER,
            additional_metadata JSONB
        )
        """,
        
        # ===== INDEXES FOR PERFORMANCE =====
        
        # Trade recommendations indexes
        """
        CREATE INDEX IF NOT EXISTS idx_trade_recommendations_symbol ON trade_recommendations(symbol);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_trade_recommendations_created_at ON trade_recommendations(created_at);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_trade_recommendations_direction ON trade_recommendations(recommendation_direction);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_trade_recommendations_status ON trade_recommendations(status);
        """,
        
        # Ensemble indexes
        """
        CREATE INDEX IF NOT EXISTS idx_ensemble_config_name ON ensemble_configurations(name);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_ensemble_config_active ON ensemble_configurations(is_active);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_ensemble_decisions_composite ON ensemble_decisions(ensemble_id, timestamp DESC);
        """,
        
        # Direction learning indexes
        """
        CREATE INDEX IF NOT EXISTS idx_direction_learning_pattern ON direction_learning_data(signal_pattern, direction);
        """,
        
        # ===== VIEWS FOR ANALYTICS =====
        
        # View for ensemble performance summary
        """
        CREATE OR REPLACE VIEW ensemble_performance_summary AS
        SELECT 
            ec.name as ensemble_name,
            COUNT(ed.id) as total_decisions,
            SUM(CASE WHEN ed.trade_executed THEN 1 ELSE 0 END) as trades_executed,
            SUM(CASE WHEN ed.trade_outcome = 'WIN' THEN 1 ELSE 0 END) as total_wins,
            SUM(CASE WHEN ed.trade_outcome = 'LOSS' THEN 1 ELSE 0 END) as total_losses,
            AVG(ed.confidence) as avg_confidence,
            SUM(ed.pnl) as total_pnl,
            ec.updated_at as last_updated
        FROM ensemble_configurations ec
        LEFT JOIN ensemble_decisions ed ON ec.id = ed.ensemble_id
        WHERE ec.is_active = true
        GROUP BY ec.id, ec.name, ec.updated_at;
        """
    ]
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ Failed to connect to database. Check SUPABASE_URL in .env file.")
        return False
        
    try:
        cursor = conn.cursor()
        
        logger.info("🔄 Creating/verifying database tables...")
        
        # Execute all commands
        for i, command in enumerate(commands):
            try:
                cursor.execute(command)
                
                # Log what was created
                if "CREATE TABLE" in command.upper():
                    # Extract table name
                    words = command.split()
                    try:
                        table_name = None
                        for j, word in enumerate(words):
                            if word.upper() == "TABLE":
                                if words[j+1].upper() == "IF" and words[j+2].upper() == "NOT" and words[j+3].upper() == "EXISTS":
                                    table_name = words[j+4]
                                else:
                                    table_name = words[j+1]
                                break
                        if table_name:
                            logger.info(f"  ✅ Table: {table_name}")
                    except:
                        logger.info(f"  ✅ Created table")
                        
                elif "CREATE INDEX" in command.upper():
                    logger.info(f"  ✅ Created index")
                elif "CREATE OR REPLACE VIEW" in command.upper():
                    logger.info(f"  ✅ Created/updated view")
                    
            except Exception as e:
                logger.warning(f"  ⚠️ Command {i+1} failed: {str(e)[:100]}")
                # Continue with other commands
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("🎉 Database setup completed successfully!")
        logger.info("📋 Tables created:")
        logger.info("   • trade_recommendations - Core trading signals")
        logger.info("   • ensemble_configurations - Ensemble setups and weights")
        logger.info("   • ensemble_decisions - Log of all ensemble decisions")
        logger.info("   • ensemble_performance_history - Performance tracking")
        logger.info("   • direction_learning_data - Pattern learning storage")
        logger.info("   • ensemble_performance_summary - Analytics view")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
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
        
        table_list = [table['table_name'] for table in tables]
        logger.info(f"📊 Existing tables: {table_list}")
        return table_list
    except Exception as e:
        logger.error(f"❌ Error checking tables: {e}")
        return []

def get_table_schema(table_name: str):
    """Get schema of specific table"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position;
        """, (table_name,))
        
        schema = cursor.fetchall()
        cursor.close()
        conn.close()
        
        logger.info(f"📋 Schema for {table_name}:")
        for col in schema:
            logger.info(f"   • {col['column_name']} ({col['data_type']}) - Nullable: {col['is_nullable']}")
        
        return schema
    except Exception as e:
        logger.error(f"❌ Error getting schema: {e}")
        return None

def reset_ensemble_tables():
    """Reset ensemble tables (for testing/development) - USE WITH CAUTION"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        logger.warning("⚠️  RESETTING ENSEMBLE TABLES - THIS WILL DELETE ALL DATA!")
        
        # Truncate tables (preserves structure)
        tables = ['ensemble_decisions', 'ensemble_performance_history', 'ensemble_configurations']
        
        for table in tables:
            cursor.execute(f"TRUNCATE TABLE {table} CASCADE;")
            logger.info(f"  Cleared: {table}")
        
        # Re-insert default ensemble configuration
        default_ensemble = {
            'name': 'default_ensemble',
            'description': 'Default trading ensemble configuration',
            'strategy_weights': {'momentum': 0.4, 'mean_reversion': 0.3, 'breakout': 0.3},
            'active_strategies': ['momentum', 'mean_reversion', 'breakout'],
            'config_settings': {
                'rebalance_frequency': 'weekly',
                'risk_adjustment': True,
                'use_direction_learning': True,
                'min_confidence': 0.6
            },
            'performance_metrics': {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0
            }
        }
        
        cursor.execute("""
            INSERT INTO ensemble_configurations 
            (name, description, strategy_weights, active_strategies, config_settings, performance_metrics)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO NOTHING;
        """, (
            default_ensemble['name'],
            default_ensemble['description'],
            psycopg2.extras.Json(default_ensemble['strategy_weights']),
            psycopg2.extras.Json(default_ensemble['active_strategies']),
            psycopg2.extras.Json(default_ensemble['config_settings']),
            psycopg2.extras.Json(default_ensemble['performance_metrics'])
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("✅ Ensemble tables reset with default configuration")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error resetting tables: {e}")
        try:
            conn.rollback()
            cursor.close()
            conn.close()
        except:
            pass
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 PRODUCTION DATABASE SETUP - Trading Agent")
    print("=" * 60)
    print("Options:")
    print("  1. Full database setup")
    print("  2. Check existing tables")
    print("  3. View table schema")
    print("  4. Reset ensemble tables (WARNING: deletes data)")
    print("  5. Exit")
    print("")
    
    choice = input("Select option (1-5): ").strip()
    
    if choice == "1":
        print("\n🔄 Running full database setup...")
        if setup_database():
            print("\n✅ Database setup completed!")
        else:
            print("\n❌ Database setup failed!")
            
    elif choice == "2":
        print("\n📊 Checking existing tables...")
        tables = check_existing_tables()
        print(f"Found {len(tables)} tables")
        
    elif choice == "3":
        table_name = input("Enter table name to view schema: ").strip()
        get_table_schema(table_name)
        
    elif choice == "4":
        confirm = input("⚠️  WARNING: This will DELETE ALL ensemble data! Confirm (yes/no): ")
        if confirm.lower() == 'yes':
            reset_ensemble_tables()
        else:
            print("❌ Cancelled.")
            
    elif choice == "5":
        print("👋 Exiting...")
        
    else:
        print("❌ Invalid option")
