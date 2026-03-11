from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ.setdefault('PYTHONDONTWRITEBYTECODE', '1')

from .runner import main

if __name__ == '__main__':
    main()
