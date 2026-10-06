"""Restore the automatic pre-v2 backup and verify its legacy contents."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

DATABASE = Path("/data/integration_simulator.db")


def main() -> None:
    backups = sorted(Path("/data/backups").glob("pre-config-v2-*.db"))
    assert backups, "automatic upgrade backup was not created"
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{DATABASE}{suffix}")
        if sidecar.exists():
            sidecar.unlink()
    shutil.copyfile(backups[-1], DATABASE)

    with sqlite3.connect(DATABASE) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        assert revision == ("006_oauth2_client_credentials",), revision
        simulation = connection.execute(
            "SELECT name, destination FROM simulations WHERE id=?",
            ("blackbox-legacy-simulation",),
        ).fetchone()
        assert simulation is not None and simulation[0] == "Retained 0.1.0 simulation"
        assert "upgrade-secret-canary" in simulation[1]
        assert connection.execute(
            "SELECT count(*) FROM event_instances WHERE id='blackbox-legacy-event'"
        ).fetchone() == (1,)


if __name__ == "__main__":
    main()
