# Version: 2
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """Get database connection for Supabase"""
    try:
        conn = psycopg2.connect(os.getenv('SUPABASE_URL'))
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return None

def setup_database():
    """Create all tables for trading bot"""
    commands = [
        # Trading Recommendations Table
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        # Trade Executions Table
        """
        CREATE TABLE IF NOT EXISTS trade_executions (
            id SERIAL PRIMARY KEY,
            recommendation_id INTEGER REFERENCES trading_recommendations(id),
            symbol VARCHAR(20) NOT NULL,
            action VARCHAR(10) NOT NULL,
            quantity DECIMAL(15, 6),
            price DECIMAL(10, 4),
            order_value DECIMAL(15, 2),
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(20) DEFAULT 'FILLED'
        )
        """,
        # Direction Learning Data Table
        """
        CREATE TABLE IF NOT EXISTS direction_learning_data (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            signal_combination JSONB NOT NULL,
            proposed_direction VARCHAR(10) NOT NULL,
            actual_direction VARCHAR(10),
            was_correct BOOLEAN,
            confidence DECIMAL(5, 4),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    ]
    
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database. Check your SUPABASE_URL.")
        return False
        
    try:
        cursor = conn.cursor()
        
        for command in commands:
            cursor.execute(command)
            print(f"✅ Table created: {command.split()[5]}")
            
        conn.commit()
        cursor.close()
        conn.close()
        
        print("🎉 Database setup completed! All tables created.")
        return True
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Setting up brand new Supabase database...")
    setup_database()
