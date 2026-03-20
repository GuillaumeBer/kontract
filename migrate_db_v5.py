import sqlite3

def migrate_v5():
    conn = sqlite3.connect('kontract.db')
    cur = conn.cursor()
    
    # Missing columns in 'opportunities' table
    missing_columns = [
        ("cv_pond", "FLOAT"),
        ("win_prob", "FLOAT"),
        ("kontract_score", "FLOAT"),
        ("floor_ratio", "FLOAT"),
        ("input_liquidity_status", "VARCHAR")
    ]
    
    for col_name, col_type in missing_columns:
        try:
            cur.execute(f"ALTER TABLE opportunities ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name} to opportunities")
        except sqlite3.OperationalError:
            print(f"Column {col_name} already exists in opportunities")
            
    conn.commit()
    conn.close()
    print("Migration v5 complete!")

if __name__ == "__main__":
    migrate_v5()
