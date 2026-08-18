from database.database import connect


def test_legacy_shadow_account_is_copied_to_default_book(tmp_path):
    path = tmp_path / "migration.db"
    conn = connect(path)
    conn.execute("INSERT INTO shadow_account VALUES(1,10000000,9000000,'created','updated')")
    conn.execute("INSERT INTO shadow_positions VALUES('AAA',10,100,0.1,70,'updated')")
    conn.execute("INSERT INTO shadow_performance VALUES('20260101',9990000,9000000,990000,0,-0.001,10000000,0,100,0)")
    conn.commit()
    conn.close()

    migrated = connect(path)
    account = migrated.execute(
        "SELECT initial_capital,cash FROM shadow_accounts WHERE portfolio_id='default'"
    ).fetchone()
    assert account == (10000000, 9000000)
    assert migrated.execute(
        "SELECT quantity FROM shadow_book_positions WHERE portfolio_id='default' AND code='AAA'"
    ).fetchone()[0] == 10
    assert migrated.execute(
        "SELECT COUNT(*) FROM shadow_book_performance WHERE portfolio_id='default'"
    ).fetchone()[0] == 1
    columns = {row[1] for row in migrated.execute("PRAGMA table_info(shadow_book_performance)")}
    assert {"target_exposure", "actual_exposure", "allocation_gap"}.issubset(columns)
    first = migrated.execute("""SELECT cash_drag,actual_exposure,target_exposure,allocation_gap
        FROM shadow_book_performance WHERE portfolio_id='default'""").fetchone()
    assert first[0] == 0
    assert first[1] == first[2]
    assert first[3] == 0
    account_columns = {row[1] for row in migrated.execute("PRAGMA table_info(shadow_accounts)")}
    assert {"strategy_version", "config_hash", "config_json", "universe_hash"}.issubset(account_columns)
    assert migrated.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_run_logs'").fetchone()
