import sqlite3

def migrate():
    conn = sqlite3.connect('kontract.db')
    cursor = conn.cursor()
    
    # Check if columns exist
    cursor.execute("PRAGMA table_info(prices)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'avg_7d' not in columns:
        print("Adding avg_7d to prices")
        cursor.execute("ALTER TABLE prices ADD COLUMN avg_7d FLOAT")
    if 'avg_30d' not in columns:
        print("Adding avg_30d to prices")
        cursor.execute("ALTER TABLE prices ADD COLUMN avg_30d FLOAT")
        
    conn.commit()
    conn.close()
    print("Migration complete")

if __name__ == "__main__":
    migrate()
