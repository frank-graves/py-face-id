"""Smoke test: verifica Python, dependencias, SQLite y (opcional) Firestore.

Ejecutar desde la raiz del proyecto:
    python -m src.smoke_test
"""
import datetime
import os
import sqlite3
import sys
import traceback

DB_PATH = "./test_smoke.db"
CREDS_PATH = os.path.join("config", "serviceAccountKey.json")


def check_imports() -> None:
    """Verifica que las dependencias esten instaladas."""
    print("Importando dependencias (puede tardar ~30s la primera vez) ...")
    import cv2
    import deepface
    import firebase_admin
    import numpy
    # sqlite3 es stdlib; ya se importo arriba
    print(
        "Imports: OK "
        f"(cv2={cv2.__version__}, "
        f"deepface={getattr(deepface, '__version__', 'n/a')}, "
        f"firebase-admin={firebase_admin.__version__}, "
        f"numpy={numpy.__version__})"
    )


def check_sqlite() -> None:
    """Crea una SQLite temporal, inserta y lee un evento."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "CREATE TABLE events("
            "id TEXT PRIMARY KEY, "
            "ts TEXT, "
            "user TEXT, "
            "tipo TEXT, "
            "veredicto TEXT"
            ")"
        )
        ahora = datetime.datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO events (id, ts, user, tipo, veredicto) "
            "VALUES (?, ?, ?, ?, ?)",
            ("smoke-1", ahora, "test_user", "entrada", "permitido"),
        )
        conn.commit()
        fila = conn.execute(
            "SELECT id, user, tipo, veredicto FROM events WHERE id = ?",
            ("smoke-1",),
        ).fetchone()
    finally:
        conn.close()

    assert fila == ("smoke-1", "test_user", "entrada", "permitido"), (
        f"Roundtrip SQLite fallo: {fila!r}"
    )
    print("SQLite: OK")


def check_firestore() -> None:
    """Si hay credenciales, escribe y lee un documento en Firestore."""
    if not os.path.exists(CREDS_PATH):
        print("Firestore: SKIP (falta config/serviceAccountKey.json)")
        return

    import firebase_admin
    from firebase_admin import credentials, firestore

    try:
        firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate(CREDS_PATH)
        firebase_admin.initialize_app(cred)

    db = firestore.client()
    doc_ref = db.collection("smoke_tests").document("smoke_test_latest")

    payload = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "origen": "smoke_test",
    }
    doc_ref.set(payload)

    snap = doc_ref.get()
    assert snap.exists, "El documento no existe tras set()"
    data = snap.to_dict()
    assert data.get("origen") == "smoke_test", f"Contenido inesperado: {data!r}"

    print("Firestore: OK")


def main() -> int:
    try:
        check_imports()
        check_sqlite()
        check_firestore()
    except Exception:
        print("\n[FAIL] Smoke test abortado:", file=sys.stderr)
        traceback.print_exc()
        return 1
    finally:
        if os.path.exists(DB_PATH):
            try:
                os.remove(DB_PATH)
            except OSError:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())