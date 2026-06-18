from setmeup.state.db import connect, init_schema


def test_init_schema_creates_tables(tmp_path):
    conn = connect(tmp_path / "setmeup.db")
    init_schema(conn)

    names = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }

    assert {"tracks", "library_index"} <= names


def test_init_schema_is_idempotent(tmp_path):
    conn = connect(tmp_path / "setmeup.db")
    init_schema(conn)
    init_schema(conn)  # must not raise

    count = conn.execute("SELECT COUNT(*) AS n FROM tracks").fetchone()["n"]
    assert count == 0
