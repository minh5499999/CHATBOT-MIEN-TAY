"""Safety checks need no AI dependencies and never write production files."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from scripts.run_isolated_tests import CHILD, ROOT, snapshot


class IsolationSafetyTests(unittest.TestCase):
    def test_write_guard_blocks_production_and_preserves_hashes(self):
        before=snapshot(ROOT)
        guard=CHILD.split('class Result')[0]
        with tempfile.TemporaryDirectory() as tmp:
            guard+='\ntry:\n    socket.socket().connect((\"203.0.113.1\",443))\nexcept PermissionError:\n    print(\"NETWORK DENIED\")\nelse:\n    raise AssertionError(\"external connection escaped\")\n'
            code=guard+'\ntry:\n    open('+repr(str(ROOT/'data'/'guard_must_not_exist.txt'))+',"w")\nexcept PermissionError:\n    print("DENIED")\nelse:\n    raise AssertionError("write escaped")\n'
            r=subprocess.run([sys.executable,'-B','-c',code],cwd=tmp,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn('DENIED',r.stdout)
            self.assertIn('NETWORK DENIED',r.stdout)
        self.assertEqual(before,snapshot(ROOT))
