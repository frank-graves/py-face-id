"""App de control de acceso biometrico facial.

Uso:
  python -m src.app               # menu interactivo
  python -m src.app --register X  # registro directo
  python -m src.app --verify      # verificacion directa
"""
import argparse
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime

import cv2
import numpy as np

# --- Configuracion ---
SETTINGS_PATH = os.path.join("config", "settings.json")
DB_PATH = "data.db"
DATASET_DIR = "dataset_rostros"
CASCADE_PATH = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
MODEL_NAME = "Facenet512"
UMBRAL = 0.40
N_FOTOS = 10


def load_settings():
    """Carga settings.json; devuelve defaults si falta o falla."""
    settings = {
        "sync_enabled": False,
        "firebase_credentials_path": "config/serviceAccountKey.json",
    }
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                settings.update(json.load(f))
        except Exception as e:
            print(f"[WARN] No se pudo leer settings.json: {e}")
    return settings


def init_db():
    """Crea tabla events si no existe y devuelve la conexion."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS events("
        "id TEXT PRIMARY KEY, ts TEXT, user TEXT, tipo TEXT, "
        "veredicto TEXT, score REAL)"
    )
    conn.commit()
    return conn


# --- Firestore (lazy, tolerante a fallos) ---
_firestore_client = None
_firestore_failed = False


def get_firestore(settings):
    """Inicializa Firestore una sola vez; None si no aplica o falla."""
    global _firestore_client, _firestore_failed
    if _firestore_failed or not settings.get("sync_enabled"):
        return None
    if _firestore_client is not None:
        return _firestore_client
    creds = settings.get("firebase_credentials_path", "")
    if not os.path.exists(creds):
        print(f"[WARN] sync_enabled=true pero falta {creds}. Sync deshabilitado.")
        _firestore_failed = True
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(credentials.Certificate(creds))
        _firestore_client = firestore.client()
        print("[OK] Firestore conectado.")
        return _firestore_client
    except Exception as e:
        print(f"[WARN] Firestore init fallo: {e}")
        _firestore_failed = True
        return None


def log_event(conn, settings, user, tipo, veredicto, score):
    """Registra evento en SQLite y (si aplica) en Firestore. Nunca levanta."""
    event_id = str(uuid.uuid4())
    ts = datetime.now().isoformat(timespec="seconds")
    try:
        conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (event_id, ts, user, tipo, veredicto, score),
        )
        conn.commit()
    except Exception as e:
        print(f"[WARN] SQLite insert fallo: {e}")
    client = get_firestore(settings)
    if client is not None:
        try:
            client.collection("events").document(event_id).set({
                "ts": ts,
                "user": user,
                "tipo": tipo,
                "veredicto": veredicto,
                "score": float(score) if score is not None else None,
            })
        except Exception as e:
            print(f"[WARN] Firestore write fallo: {e}")


# --- Vision ---
def build_embedding(frame):
    """Calcula embedding normalizado del primer rostro (enforce_detection=False)."""
    from deepface import DeepFace
    reps = DeepFace.represent(img_path=frame, model_name=MODEL_NAME, enforce_detection=False)
    if not reps:
        return None
    vec = np.asarray(reps[0]["embedding"], dtype=np.float32)
    n = np.linalg.norm(vec)
    return vec / n if n > 0 else vec


def detect_face_rect(gray, detector):
    """Devuelve el rectangulo del rostro mas grande o None."""
    faces = detector.detectMultiScale(gray, 1.1, 5)
    if len(faces) == 0:
        return None
    return max(faces, key=lambda f: f[2] * f[3])


# --- Registro ---
def register_user(cap, detector, name):
    """Captura N fotos y guarda embeddings.npy para el usuario."""
    out_dir = os.path.join(DATASET_DIR, name)
    os.makedirs(out_dir, exist_ok=True)
    collected = []
    print(f"[INFO] Registrando '{name}'. ESPACIO por foto, Q para abortar.")
    while len(collected) < N_FOTOS:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rect = detect_face_rect(gray, detector)
        if rect is not None:
            x, y, w, h = rect
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(
            frame,
            f"REGISTRO {name}  {len(collected)}/{N_FOTOS}  [ESPACIO] foto  [Q] abortar",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2,
        )
        cv2.imshow("Control de Acceso", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("[INFO] Registro abortado.")
            return
        if key == 32:  # ESPACIO
            print(f"[..] Embedding {len(collected) + 1}/{N_FOTOS} ...")
            emb = build_embedding(frame)
            if emb is not None:
                collected.append(emb)
                print(f"[OK] Captura {len(collected)}/{N_FOTOS}")
            else:
                print("[WARN] Sin rostro valido; reintenta.")
    if len(collected) == 0:
        print("[ERROR] Sin capturas validas.")
        return
    np.save(os.path.join(out_dir, "embeddings.npy"), np.stack(collected))
    print(f"[OK] Guardados {len(collected)} embeddings en {out_dir}/embeddings.npy")


# --- Verificacion ---
def load_gallery():
    """Carga embeddings por usuario (promediados y normalizados)."""
    gallery = {}
    if not os.path.isdir(DATASET_DIR):
        return gallery
    for name in os.listdir(DATASET_DIR):
        path = os.path.join(DATASET_DIR, name, "embeddings.npy")
        if not os.path.exists(path):
            continue
        try:
            arr = np.load(path)
            if arr.ndim == 2 and arr.shape[0] > 0:
                mean = arr.mean(axis=0)
                n = np.linalg.norm(mean)
                gallery[name] = mean / n if n > 0 else mean
        except Exception as e:
            print(f"[WARN] No se pudo cargar {path}: {e}")
    return gallery


def verify_frame(conn, settings, frame):
    """Verifica el frame y devuelve (veredicto, usuario, score)."""
    emb = build_embedding(frame)
    if emb is None:
        log_event(conn, settings, "desconocido", "acceso", "denegado", 0.0)
        return "denegado", "desconocido", 0.0
    gallery = load_gallery()
    if not gallery:
        print("[WARN] No hay usuarios registrados.")
        log_event(conn, settings, "desconocido", "acceso", "denegado", 0.0)
        return "denegado", "desconocido", 0.0
    best_user, best_score = None, -1.0
    for user, gvec in gallery.items():
        score = float(np.dot(emb, gvec))
        if score > best_score:
            best_user, best_score = user, score
    veredicto = "permitido" if best_score >= UMBRAL else "denegado"
    usuario_log = best_user if veredicto == "permitido" else (best_user or "desconocido")
    log_event(conn, settings, usuario_log, "acceso", veredicto, best_score)
    return veredicto, best_user or "desconocido", best_score


def show_result(frame, veredicto, user, score):
    """Muestra el resultado 3 segundos (verde/rojo)."""
    color = (0, 200, 0) if veredicto == "permitido" else (0, 0, 220)
    if veredicto == "permitido":
        msg = f"ACCESO CONCEDIDO: {user} ({score:.2f})"
    else:
        msg = f"ACCESO DENEGADO ({score:.2f})"
    disp = frame.copy()
    cv2.rectangle(disp, (0, 0), (disp.shape[1], 60), color, -1)
    cv2.putText(disp, msg, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imshow("Control de Acceso", disp)
    cv2.waitKey(3000)


# --- Loop principal ---
def run(register_name=None, verify_only=False):
    """Punto de entrada de la app."""
    settings = load_settings()
    conn = init_db()
    detector = cv2.CascadeClassifier(CASCADE_PATH)
    if detector.empty():
        print("[ERROR] No se cargo el Haar cascade.")
        return 1
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] No se pudo abrir la camara.")
        return 1
    try:
        if register_name:
            register_user(cap, detector, register_name)
            return 0

        if verify_only:
            print("[INFO] ESPACIO para verificar, Q para salir.")
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                rect = detect_face_rect(gray, detector)
                if rect is not None:
                    x, y, w, h = rect
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(frame, "[ESPACIO] verificar  [Q] salir",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.imshow("Control de Acceso", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                if key == 32:
                    v, u, s = verify_frame(conn, settings, frame)
                    print(f"[RESULT] {v} user={u} score={s:.3f}")
                    show_result(frame, v, u, s)
            return 0

        # Menu interactivo
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rect = detect_face_rect(gray, detector)
            if rect is not None:
                x, y, w, h = rect
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, "[R] Registrar  [V] Verificar  [Q] Salir",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.imshow("Control de Acceso", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            if key == ord('r'):
                name = input("Nombre del usuario: ").strip()
                if name:
                    register_user(cap, detector, name)
            if key == ord('v'):
                v, u, s = verify_frame(conn, settings, frame)
                print(f"[RESULT] {v} user={u} score={s:.3f}")
                show_result(frame, v, u, s)
        return 0
    finally:
        cap.release()
        cv2.destroyAllWindows()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Control de acceso biometrico facial")
    parser.add_argument("--register", metavar="NOMBRE", help="Registrar usuario y salir")
    parser.add_argument("--verify", action="store_true", help="Modo verificacion directa")
    args = parser.parse_args()
    try:
        return run(register_name=args.register, verify_only=args.verify)
    except Exception:
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())