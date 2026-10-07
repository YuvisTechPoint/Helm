import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for rel in ("packages/core", "apps/youtube", "apps/acquisition", "apps/api"):
    sys.path.insert(0, str(ROOT / rel))

from youtube.worker import main

if __name__ == "__main__":
    asyncio.run(main())
