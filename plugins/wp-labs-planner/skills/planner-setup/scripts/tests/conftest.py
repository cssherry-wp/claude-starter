from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))        # planner-setup/scripts — planner package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent)) # planner-setup — status_check.py
