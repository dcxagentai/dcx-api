import os
import sys

# Compute path to 'dcx' directory (1 level up from dcx_test)
current_dir = os.path.dirname(os.path.abspath(__file__))
dcx_project_dir = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, dcx_project_dir)

import psycopg2
from storage.db_config import DB_CONFIG

# Change this to None to get ALL tables, or a string like "stephen_dcx_" to filter
TABLE_PREFIX = "stephen_dcx_"

def get_schema_summary(table_prefix=None):
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        output = []
        output.append("="*60)
        output.append("STEPHEN DCX ACTUAL SCHEMA FULL REPORT")
        output.append(f"Generated on {conn.get_dsn_parameters()['host']}:{conn.get_dsn_parameters()['port']}")
        output.append(f"Database: {DB_CONFIG['dbname']}")
        output.append("="*60)
        output.append("\n")

        # 1. Get all tables (equivalent to \dt)
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        tables = [r[0] for r in cur.fetchall()]
        if table_prefix:
            tables = [t for t in tables if t.startswith(table_prefix)]
        
        output.append("TABLE LIST (\\dt):")
        output.append("-" * 30)
        for t in tables:
            output.append(f"- {t}")
        output.append("\n")

        # 2. Get detailed info for each table (equivalent to \d table_name)
        for table in tables:
            output.append("="*60)
            output.append(f"TABLE: {table}")
            output.append("="*60)
            
            # Columns info
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position;
            """, (table,))
            columns = cur.fetchall()
            
            output.append(f"{'COLUMN':<30} | {'TYPE':<25} | {'NULL?':<8} | {'DEFAULT'}")
            output.append("-" * 80)
            for col in columns:
                output.append(f"{col[0]:<30} | {col[1]:<25} | {col[2]:<8} | {col[3] or ''}")
            
            output.append("\nFOREIGN KEYS:")
            cur.execute("""
                SELECT
                    tc.constraint_name, 
                    kcu.column_name, 
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name 
                FROM 
                    information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name=%s;
            """, (table,))
            fks = cur.fetchall()
            if fks:
                for fk in fks:
                    output.append(f"- {fk[1]} -> {fk[2]}({fk[3]}) [{fk[0]}]")
            else:
                output.append("- None")
                
            output.append("\nPRIMARY KEYS / UNIQUE:")
            cur.execute("""
                SELECT tc.constraint_name, kcu.column_name, tc.constraint_type
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                WHERE tc.table_name = %s AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE');
            """, (table,))
            pks = cur.fetchall()
            if pks:
                for pk in pks:
                    output.append(f"- {pk[2]}: {pk[1]} [{pk[0]}]")
            else:
                output.append("- None")

            output.append("\n")

        # Save to file in the same directory as the script
        filename = f"db_schema_{table_prefix}.txt" if table_prefix else "db_schema_actual_full.txt"
        report_path = os.path.join(current_dir, filename)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(output))
            
        print(f"✅ Full schema report generated: {report_path}")
        
    except Exception as e:
        print(f"❌ Error generating schema report: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    get_schema_summary(TABLE_PREFIX)
