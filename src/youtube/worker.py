import asyncio
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from acquisition.activities import ACQUISITION_ACTIVITIES
from acquisition.workflows import ACQUISITION_WORKFLOWS
from core.config import get_settings
from youtube.activities import YOUTUBE_ACTIVITIES
from youtube.workflows import (
    CollectMetricsWorkflow,
    OptimizeVideoWorkflow,
    ProduceOneWorkflow,
    ProducePrivateWorkflow,
    WeeklyPlanWorkflow,
)


async def main() -> None:
    from core.container import bootstrap

    settings = get_settings()
    bootstrap(settings)
    client = await Client.connect(settings.temporal_address)
    with ThreadPoolExecutor(max_workers=settings.worker_threads) as executor:
        worker = Worker(
            client,
            task_queue=settings.temporal_task_queue,
            workflows=[
                ProduceOneWorkflow,
                ProducePrivateWorkflow,
                WeeklyPlanWorkflow,
                CollectMetricsWorkflow,
                OptimizeVideoWorkflow,
                *ACQUISITION_WORKFLOWS,
            ],
            activities=[*YOUTUBE_ACTIVITIES, *ACQUISITION_ACTIVITIES],
            activity_executor=executor,
        )
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
