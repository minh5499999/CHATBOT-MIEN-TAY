"""Tải trước trọng số khi có mạng; không gửi câu hỏi hoặc hội thoại.

python scripts/chuan_bi_mo_hinh.py
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from huggingface_hub import snapshot_download
    from backend.chatbot.cau_hinh import doc_cau_hinh_cat_doan
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    models = [doc_cau_hinh_cat_doan()["ten_mo_hinh"]]
    for model in models:
        print(f"Chuẩn bị {model}")
        snapshot_download(model, ignore_patterns=["*.bin", "*.onnx", "*.h5", "*.msgpack", "*.gguf"])
    print("Đã tải xong. Chatbot có thể dùng cache cục bộ.")


if __name__ == "__main__":
    main()
