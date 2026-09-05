import sqlite3
import os

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, 'fitfuel.db')
SCHEMA_PATH = os.path.join(DB_DIR, 'schema.sql')

def init_db():
    print(f"Initializing database at {DB_PATH}")
    
    # Read the schema file
    with open(SCHEMA_PATH, 'r') as f:
        schema = f.read()

    # Connect to database (creates it if it doesn't exist)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Execute schema
    cursor.executescript(schema)
    
    conn.commit()
    conn.close()
    
    print("Database initialized successfully.")

if __name__ == '__main__':
    init_db()
