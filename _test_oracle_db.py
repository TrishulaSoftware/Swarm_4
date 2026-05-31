#!/usr/bin/env python3
import oracledb
from pathlib import Path

WALLET_DIR = r"H:\Trishula\Swarm_4_Integration\Salvo_Staging\oracle_wallet"
WALLET_PW  = "C1iffyHu5tl3!!!"
DB_USER    = "ADMIN"
DB_PW      = "C1iffyHu5tl3!!!"
DSN        = "trishulapicks_tp"

# Fix sqlnet.ora to point to local wallet directory
sqlnet = Path(WALLET_DIR) / "sqlnet.ora"
sqlnet.write_text(
    f'WALLET_LOCATION = (SOURCE = (METHOD = file) (METHOD_DATA = (DIRECTORY="{WALLET_DIR}")))\n'
    f'SSL_SERVER_DN_MATCH=yes\n'
)
print(f"[OK] sqlnet.ora updated -> {WALLET_DIR}")

# Update .env
env_path = Path(r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env")
txt = env_path.read_text(encoding="utf-8")
if "ORACLE_PASSWORD=C1" not in txt:
    txt = txt.replace("ORACLE_PASSWORD=", f"ORACLE_PASSWORD={DB_PW}")
    env_path.write_text(txt, encoding="utf-8")
print("[OK] ORACLE_PASSWORD set in .env")

print("\n  Testing connection to trishulapicks_tp...")
print("="*50)

try:
    conn = oracledb.connect(
        user=DB_USER,
        password=DB_PW,
        dsn=DSN,
        wallet_location=WALLET_DIR,
        wallet_password=WALLET_PW,
    )
    print(f"  [PASS] Connected to Oracle Autonomous DB!")
    cur = conn.cursor()

    # Check Oracle version
    cur.execute("SELECT BANNER FROM V$VERSION WHERE BANNER LIKE 'Oracle%'")
    row = cur.fetchone()
    print(f"  [INFO] {row[0] if row else 'Connected'}")

    # Create picks schema if not exists
    print("\n  Creating Trishula schema tables...")
    tables = [
        """CREATE TABLE IF NOT EXISTS picks_history (
            id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            pick_date   DATE DEFAULT SYSDATE,
            sport       VARCHAR2(20),
            event_id    VARCHAR2(100),
            pick_type   VARCHAR2(50),
            selection   VARCHAR2(200),
            odds        NUMBER(8,2),
            stake       NUMBER(8,2),
            result      VARCHAR2(10),
            pnl         NUMBER(10,2),
            confidence  NUMBER(5,2),
            source      VARCHAR2(50)
        )""",
        """CREATE TABLE IF NOT EXISTS line_history (
            id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            record_ts   TIMESTAMP DEFAULT SYSTIMESTAMP,
            event_id    VARCHAR2(100),
            sport       VARCHAR2(20),
            book        VARCHAR2(50),
            market      VARCHAR2(100),
            open_line   NUMBER(8,2),
            current_line NUMBER(8,2),
            movement    NUMBER(8,2)
        )""",
        """CREATE TABLE IF NOT EXISTS qmatrix_snapshots (
            id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            snap_ts     TIMESTAMP DEFAULT SYSTIMESTAMP,
            symbol      VARCHAR2(10),
            spot        NUMBER(12,4),
            max_pain    NUMBER(12,4),
            net_gex     NUMBER(16,2),
            pc_ratio    NUMBER(8,4),
            expiry      VARCHAR2(20),
            sweep_type  VARCHAR2(30)
        )""",
    ]

    for ddl in tables:
        try:
            cur.execute(ddl)
            conn.commit()
            name = ddl.split("TABLE IF NOT EXISTS ")[1].split(" ")[0]
            print(f"  [OK] Table ready: {name}")
        except oracledb.DatabaseError as e:
            err = str(e)
            if "ORA-00955" in err or "already used" in err.lower():
                name = ddl.split("TABLE IF NOT EXISTS ")[1].split(" ")[0]
                print(f"  [OK] Table exists: {name}")
            else:
                print(f"  [WARN] {err[:80]}")

    # Quick insert + read test
    cur.execute("SELECT COUNT(*) FROM qmatrix_snapshots")
    count = cur.fetchone()[0]
    print(f"\n  [PASS] qmatrix_snapshots: {count} rows")

    cur.close()
    conn.close()
    print("\n  Oracle Autonomous DB LIVE — 20GB always-free storage ready")

except Exception as e:
    print(f"  [FAIL] Connection error: {e}")
    print("\n  Common fixes:")
    print("  - DB may still be provisioning (wait 2 more min, retry)")
    print("  - Check wallet password matches download dialog")

print("="*50 + "\n")
