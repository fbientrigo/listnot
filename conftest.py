"""Ensure the repo root is importable so ``apps.*`` entry points resolve in tests.

The installed package ``pucv_aq_qc`` (src layout, editable install) is importable
regardless; ``apps/`` lives at the repo root and needs the root on sys.path.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
