r"""Kiểm tra kết nối, mật khẩu và dữ liệu Neo4j; không in mật khẩu, không ghi dữ liệu.

Chạy tại thư mục chứa app.py: .venv\Scripts\python.exe scripts/kiem_tra_neo4j.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from backend.chatbot.cau_hinh import doc_cau_hinh
    from backend.chatbot.kho_neo4j import chay, ket_noi
    try:
        chay("RETURN 1 AS kiem_tra")
        print("Kết nối thành công: tên đăng nhập và mật khẩu đúng.")
        kho = doc_cau_hinh()["kho_vector"]
        rows = chay("MATCH (k:Kho {ten: $ten}) RETURN k.ten AS ten, k.so_doan AS so_doan", ten=kho)
        if not rows:
            print("Chưa có dữ liệu kho backend.chatbot. Chạy scripts/nap_neo4j.py.")
            return 2
        for row in rows:
            print(f"Kho: {row['ten']} | Số đoạn theo metadata: {row['so_doan']}")
        counts = chay("MATCH (d:Doan {kho: $kho}) RETURN count(d) AS n", kho=kho)
        print(f"Số đoạn thực tế: {counts[0]['n']}")
        indexes = chay("SHOW VECTOR INDEXES YIELD name, state RETURN name, state")
        for row in indexes:
            print(f"Chỉ mục: {row['name']} | Trạng thái: {row['state']}")
        if counts[0]['n'] != rows[0]['so_doan']:
            print("Số đoạn không khớp; cần nạp lại kho.")
            return 3
        if not any(r['name'] == 'doan_vector' and r['state'] == 'ONLINE' for r in indexes):
            print("Chỉ mục vector chưa sẵn sàng.")
            return 4
        return 0
    except Exception as exc:
        code = getattr(exc, "code", "")
        if "Unauthorized" in code or "Authentication" in code:
            print("Tên đăng nhập hoặc mật khẩu chưa đúng. Kiểm tra .env.")
        else:
            print(f"Không kết nối/kiểm tra được Neo4j ({type(exc).__name__}). Kiểm tra instance đã chạy và cổng trong .env.")
        return 1
    finally:
        if ket_noi.cache_info().currsize:
            ket_noi().close()


if __name__ == "__main__":
    sys.exit(main())
