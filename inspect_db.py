import sqlite3

def inspect_schema():
    conn = sqlite3.connect('kontract.db')
    cur = conn.cursor()
    
    tables = ['opportunities', 'prices', 'skins', 'collections', 'user_alerts', 'tradeup_pool']
    for table in tables:
        print(f"--- Table: {table} ---")
        try:
            cur.execute(f"PRAGMA table_info({table})")
            columns = cur.fetchall()
            for col in columns:
                print(col)
        except Exception as e:
            print(f"Error inspecting {table}: {e}")
            
    conn.close()

if __name__ == "__main__":
    inspect_schema()
