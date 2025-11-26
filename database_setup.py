# Version: 1
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

load_dotenv()

def get_db_connection(database="postgres"):
    """Get database connection"""
    return psycopg2.connect(
        host=os.getenv('SUPABASE_HOST', os.getenv('SUPABASE_URL').replace('postgresql://', '').split(':')[0]),
        database=database,
        user=os.getenv('SUPABASE_USER', 'postgres'),
        password=os.getenv('SUPABASE_PASSWORD', os.getenv('SUPABASE_KEY')),
        port=os.getenv('SUPABASE_PORT', '5432')
    )

def create_database():
    """Create database if it doesn't exist"""
    try:
        # Connect to default postgres database to create our app database
        conn = get_db_connection("postgres")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        db_name = os.getenv('SUPABASE_DB', 'trading_bot')
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (db_name,))
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(f'CREATE DATABASE "{db_name}"')
            print(f"✅ Database '{db_name}' created successfully")
        else:
            print(f"✅ Database '{db_name}' already exists")
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")

def create_tables():
    """Create all necessary tables"""
    commands = (
        """
        CREATE TABLE IF NOT EXISTS trading_recommendations (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL,
            strategy VARCHAR(100),
            direction VARCHAR(10),
            confidence VARCHAR(10),
            price DECIMAL(10, 4),
            reasoning TEXT,
            model_details JSONB,
            consensus_breakdown JSONB,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            market_conditions JSONB,
            etf_mode BOOLEAN DEFAULT FALSE,
            discord_message_id VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS trade_executions (
            id SERIAL PRIMARY KEY,
            recommendation_id INTEGER REFERENCES trading_recommendations(id),
            action VARCHAR(10) NOT NULL,
            quantity DECIMAL(15, 6),
            price DECIMAL(10, 4),
            order_value DECIMAL(15, 2),
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(20) DEFAULT 'FILLED',
            profit_loss DECIMAL(10, 2),
            notes TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS direction_learning_data (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            signal_combination JSONB NOT NULL,
            proposed_direction VARCHAR(10) NOT NULL,
            actual_direction VARCHAR(10),
            was_correct BOOLEAN,
            confidence DECIMAL(5, 4),
            market_conditions JSONB,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            strategy_used VARCHAR(100),
            price_at_signal DECIMAL(10, 4),
            price_outcome DECIMAL(10, 4),
            outcome_percentage DECIMAL(8, 4)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ensemble_performance (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_trades INTEGER DEFAULT 0,
            winning_trades INTEGER DEFAULT 0,
            win_rate DECIMAL(5, 4),
            total_return DECIMAL(8, 4),
            current_drawdown DECIMAL(8, 4),
            portfolio_value DECIMAL(15, 2),
            performance_data JSONB
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS market_data_log (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            price DECIMAL(10, 4),
            volume BIGINT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            strategy VARCHAR(100),
            pattern VARCHAR(100),
            additional_data JSONB
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS backtest_results (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL,
            strategy_name VARCHAR(100),
            total_trades INTEGER,
            win_rate DECIMAL(5, 4),
            total_return DECIMAL(8, 4),
            sharpe_ratio DECIMAL(8, 4),
            max_drawdown DECIMAL(8, 4),
            backtest_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_recommendations_ticker ON trading_recommendations(ticker);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_recommendations_timestamp ON trading_recommendations(timestamp);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_learning_symbol ON direction_learning_data(symbol);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_learning_timestamp ON direction_learning_data(timestamp);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_learning_combination ON direction_learning_data USING gin(signal_combination);
        """
    )
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for command in commands:
            cursor.execute(command)
            
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ All tables created successfully")
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")

def setup_database():
    """Main function to setup complete database"""
    print("🚀 Starting database setup...")
    
    # Check environment variables
    required_vars = ['SUPABASE_URL', 'SUPABASE_KEY']
    for var in required_vars:
        if not os.getenv(var):
            print(f"❌ Missing required environment variable: {var}")
            return False
    
    print("✅ Environment variables check passed")
    
    # Create database
    create_database()
    
    # Create tables
    create_tables()
    
    print("🎉 Database setup completed successfully!")
    return True

if __name__ == "__main__":
    setup_database()
