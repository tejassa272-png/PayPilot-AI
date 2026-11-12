import os
import psycopg2
from dotenv import load_dotenv
from database import init_db

load_dotenv()

def seed_database():
    init_db()
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    
    # Clear existing data for a clean demo run
    cursor.execute("TRUNCATE TABLE customers, audit_logs RESTART IDENTITY CASCADE;")
    
    # Seed the baseline demo customer and their Reliability Score
    cursor.execute("""
        INSERT INTO customers (id, name, email, reliability_score) 
        VALUES ('CUST-999', 'Acme Corp', 'billing@acmecorp.com', 85.0)
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Database seeded and ready for the Hackathon Demo!")

if __name__ == "__main__":
    seed_database()