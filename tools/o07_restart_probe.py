"""O07 - prova de consistencia de dados apos shutdown gracioso + restart.

Uso:
    python tools/o07_restart_probe.py write <marker>
    python tools/o07_restart_probe.py read <marker>

Le/escreve direto no SQLite usado pelo container (DATABASE_URL local),
sem depender de rotas da API, para isolar o teste de infraestrutura
(volume + restart) da logica de negocio. Nao adiciona funcionalidade
nova ao produto - e uma ferramenta de CI, equivalente em escopo ao
shim tools/ffmpeg ja existente no repositorio.
"""
import sqlite3
import sys

DB_PATH = "/app/data/adintelligence.db"


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ("write", "read"):
        print("uso: o07_restart_probe.py [write|read] <marker>")
        sys.exit(2)

    action, marker = sys.argv[1], sys.argv[2]
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "CREATE TABLE IF NOT EXISTS o07_restart_probe ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "marker TEXT NOT NULL, "
        "created_at TEXT NOT NULL)"
    )

    if action == "write":
        con.execute(
            "INSERT INTO o07_restart_probe (marker, created_at) "
            "VALUES (?, datetime('now'))",
            (marker,),
        )
        con.commit()
        print(f"WRITE_OK marker={marker}")
    else:
        row = con.execute(
            "SELECT id, marker, created_at FROM o07_restart_probe WHERE marker = ?",
            (marker,),
        ).fetchone()
        if row:
            print(f"READ_OK id={row[0]} marker={row[1]} created_at={row[2]}")
        else:
            print("READ_MISSING")
            sys.exit(1)

    con.close()


if __name__ == "__main__":
    main()
