# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import logging
from asyncio import Queue, all_tasks, current_task, gather, get_running_loop
from copy import deepcopy
from pathlib import Path

from .message import (
    DisablePrintMessage,
    EnablePrintMessage,
    EnableVerboseMessage,
    LogMessage,
    SetWorkdirMessage,
    TeardownMessage,
)
from .writer import FileWriter, PrintWriter, ReportErrorWriter


async def listen(queue: Queue) -> None:
    from ..base import setup as setup_logging

    setup_logging(queue)

    loop = get_running_loop()

    print_writer = PrintWriter(levelno=25)  # fmriprep's IMPORTANT
    log_writer = FileWriter(levelno=logging.DEBUG)
    err_writer = FileWriter(levelno=logging.WARNING)
    report_err_writer = ReportErrorWriter(levelno=logging.ERROR)

    writers = [print_writer, log_writer, err_writer, report_err_writer]

    [loop.create_task(writer.start()) for writer in writers]

    subscribers = [writer.queue for writer in writers]

    while True:
        message = await loop.run_in_executor(None, queue.get)

        if isinstance(message, LogMessage):
            for subscriber in subscribers:
                messagecopy = deepcopy(message)  # allow subscribers to modify message
                await subscriber.put(messagecopy)

        elif isinstance(message, SetWorkdirMessage):
            workdir: Path = message.workdir

            workdir.mkdir(exist_ok=True, parents=True)

            log_writer.filename = workdir / "log.txt"
            log_writer.can_write.set()

            err_writer.filename = workdir / "err.txt"
            err_writer.can_write.set()

            report_err_writer.filename = workdir / "reports" / "reporterror.js"
            report_err_writer.can_write.set()

        elif isinstance(message, EnableVerboseMessage):
            print_writer.levelno = logging.DEBUG

        elif isinstance(message, EnablePrintMessage):
            print_writer.can_write.set()

        elif isinstance(message, DisablePrintMessage):
            print_writer.can_write.clear()

        elif isinstance(message, TeardownMessage):
            # make sure that all writers have finished writing
            await gather(*[subscriber.join() for subscriber in subscribers])

            # then cancel all tasks
            tasks = [t for t in all_tasks() if t is not current_task()]

            [task.cancel() for task in tasks]

            await gather(*tasks)
            loop.stop()

            break

        else:
            logging.error(f'Logging worker received unknown message "{message}"')

        queue.task_done()
