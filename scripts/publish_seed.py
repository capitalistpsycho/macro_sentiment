"""
Publish the local database to GitHub -> Streamlit Cloud.

    python scripts/publish_seed.py             # publish what's already in cache/
    python scripts/publish_seed.py --refresh   # run_macro.py --full first
    python scripts/publish_seed.py --dry-run   # merge + report, don't commit

Why this exists instead of `cp cache/macro.db data/seed_macro.db`:

The GitHub Action refreshes and commits the seed every weekday, so the cloud
copy accumulates signal history on days this machine was off. The local copy in
turn holds rows the Action can't produce. A straight copy in either direction
silently destroys the other side's history — so this unions them instead:

  pull -> merge (local wins on conflicting keys) -> write both -> commit -> push

Every table except pm_journal has a natural primary key, so INSERT OR REPLACE
is a clean union; the journal is deduped on (date, note) because both runners
log the same auto regime-change note at different timestamps.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "cache", "macro.db")
SEED = os.path.join(ROOT, "data", "seed_macro.db")
STATUS = os.path.join("data", "refresh_status.json")

SKIP_TABLES = {"sqlite_sequence", "pm_journal"}


def git(*args: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout.strip()


def tables(con: sqlite3.Connection, schema: str = "main") -> list[str]:
    return [r[0] for r in con.execute(
        f"SELECT name FROM {schema}.sqlite_master WHERE type='table'")]


def merge(seed: str, local: str, out: str) -> dict:
    """Union `local` into a copy of `seed` at `out`. Local wins on key conflicts."""
    shutil.copyfile(seed, out)
    con = sqlite3.connect(out)
    con.execute("ATTACH ? AS loc", (local,))
    report = {}

    seed_tables, local_tables = set(tables(con)), set(tables(con, "loc"))
    for t in sorted(local_tables - SKIP_TABLES):
        before = con.execute(f"SELECT COUNT(*) FROM main.{t}").fetchone()[0] \
            if t in seed_tables else 0
        if t not in seed_tables:
            # Table the cloud seed has never seen — carry it over wholesale.
            ddl = con.execute(
                "SELECT sql FROM loc.sqlite_master WHERE type='table' AND name=?",
                (t,)).fetchone()[0]
            con.execute(ddl)
        cols = ",".join(f'"{r[1]}"' for r in con.execute(f"PRAGMA loc.table_info({t})"))
        con.execute(f"INSERT OR REPLACE INTO main.{t} ({cols}) SELECT {cols} FROM loc.{t}")
        after = con.execute(f"SELECT COUNT(*) FROM main.{t}").fetchone()[0]
        report[t] = (before, after)

    if "pm_journal" in local_tables and "pm_journal" in seed_tables:
        before = con.execute("SELECT COUNT(*) FROM main.pm_journal").fetchone()[0]
        seen = {r for r in con.execute("SELECT date, note FROM main.pm_journal")}
        for ts, date, regime, note in con.execute(
                "SELECT ts, date, regime, note FROM loc.pm_journal").fetchall():
            if (date, note) not in seen:
                con.execute(
                    "INSERT INTO main.pm_journal(ts, date, regime, note) VALUES(?,?,?,?)",
                    (ts, date, regime, note))
                seen.add((date, note))
        after = con.execute("SELECT COUNT(*) FROM main.pm_journal").fetchone()[0]
        report["pm_journal"] = (before, after)

    con.commit()
    con.execute("DETACH loc")
    con.execute("VACUUM")
    con.close()
    return report


def write_status() -> None:
    """Refresh data/refresh_status.json so a local push reports its own coverage."""
    sys.path.insert(0, ROOT)
    try:
        from config.secrets import get_secret
        for name in ("FRED_API_KEY", "FMP_API_KEY"):
            os.environ[f"{name.split('_')[0]}_KEY_PRESENT"] = \
                "true" if get_secret(name) else "false"
    except Exception:
        pass
    subprocess.run([sys.executable, os.path.join("scripts", "record_coverage.py")],
                   cwd=ROOT, capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish the local DB to GitHub/Cloud")
    ap.add_argument("--refresh", action="store_true", help="run run_macro.py --full first")
    ap.add_argument("--dry-run", action="store_true", help="merge and report, no commit")
    args = ap.parse_args()

    if args.refresh:
        print("== Refreshing data ==")
        if subprocess.run([sys.executable, "run_macro.py", "--full"], cwd=ROOT).returncode:
            raise SystemExit("Refresh failed — not publishing.")

    if not os.path.exists(CACHE):
        raise SystemExit(f"No {CACHE} — run `python run_macro.py --full` first.")

    print("== Pulling the cloud seed ==")
    if git("status", "--porcelain", "--", "data/seed_macro.db"):
        raise SystemExit("data/seed_macro.db has uncommitted edits — resolve before publishing.")
    git("fetch", "origin")
    behind = git("rev-list", "--count", "HEAD..origin/main")
    git("pull", "--rebase", "origin", "main") if behind != "0" else None
    print(f"   {behind} new commit(s) from the Action")

    print("== Merging cloud history with local ==")
    tmp = os.path.join(tempfile.gettempdir(), "macro_publish_merge.db")
    report = merge(SEED, CACHE, tmp)
    for t, (before, after) in sorted(report.items()):
        flag = f"  (+{after - before})" if after != before else ""
        print(f"   {t:18} {before:7} -> {after:7}{flag}")

    if args.dry_run:
        print(f"\nDry run — merged DB left at {tmp}, nothing committed.")
        return 0

    shutil.copyfile(tmp, SEED)
    shutil.copyfile(tmp, CACHE)

    # Gate on the seed: refresh_status.json carries a timestamp that always
    # differs, so writing it first would commit noise on a no-op publish.
    git("add", "data/seed_macro.db")
    if not git("diff", "--cached", "--name-only"):
        print("\nSeed unchanged — nothing to publish (the cloud already has this data).")
        return 0
    write_status()
    git("add", STATUS)

    from datetime import date
    git("commit", "-m", f"chore: refresh macro seed from local run ({date.today()})")
    print("== Pushing ==")
    git("push", "origin", "main")
    print(f"\nPublished {git('rev-parse', '--short', 'HEAD')} -> Streamlit Cloud will redeploy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
