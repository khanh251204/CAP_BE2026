import os
import sys

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.configs.firebase import db


def delete_all_notifications():
    print("[Firebase] Dang ket noi toi Firestore collection 'notifications'...")
    collection_ref = db.collection("notifications")
    docs = list(collection_ref.stream())
    total_docs = len(docs)

    if total_docs == 0:
        print("[Firebase] Khong co thong bao nao trong collection 'notifications'.")
        return 0

    print(f"[Firebase] Tim thay {total_docs} thong bao. Dang tien hanh xoa theo batch...")

    batch_size = 400
    deleted_count = 0

    for i in range(0, total_docs, batch_size):
        chunk = docs[i : i + batch_size]
        batch = db.batch()
        for doc in chunk:
            batch.delete(doc.reference)
        batch.commit()
        deleted_count += len(chunk)
        print(f"[Firebase] Da xoa {deleted_count}/{total_docs} thong bao...")

    print(f"[Firebase] Hoan tat! Da xoa thanh cong toan bo {deleted_count} thong bao cu trong Firebase Firestore.")
    return deleted_count


if __name__ == "__main__":
    delete_all_notifications()
