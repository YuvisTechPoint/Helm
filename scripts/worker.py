"""Start the Temporal worker."""

import asyncio

from scripts._bootstrap import install


def main() -> None:
    install()
    from youtube.worker import main as worker_main

    asyncio.run(worker_main())


if __name__ == "__main__":
    main()
