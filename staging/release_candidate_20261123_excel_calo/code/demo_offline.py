"""Start the candidate with a pinned, already available local model."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


def check_model(model, hashes):
    for name, expected in hashes.items():
        path = model / name
        if not path.is_file():
            raise ValueError(f'Thiếu file mô hình {name}')
        with path.open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != expected:
                raise ValueError(f'Sai SHA-256 mô hình {name}')


def main():
    code = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', required=True, type=Path)
    parser.add_argument('--port', type=int, default=8501)
    args = parser.parse_args()
    model = args.model_dir.resolve()
    try:
        check_model(model, json.loads((code/'model-sha256.json').read_bytes()))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    os.environ.update(CHATBOT_MODEL_DIR=str(model), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      HF_HUB_DISABLE_TELEMETRY='1', LANGSMITH_TRACING='false',
                      LANGCHAIN_TRACING_V2='false', PYTHON_DOTENV_DISABLED='1')
    os.chdir(code.parents[2])
    from streamlit.web import cli
    sys.argv=['streamlit','run',str(code/'app.py'),'--server.address','127.0.0.1',
              '--server.port',str(args.port),'--server.headless','true',
              '--server.enableStaticServing','true','--browser.gatherUsageStats','false']
    return cli.main()


if __name__=='__main__':
    raise SystemExit(main())

