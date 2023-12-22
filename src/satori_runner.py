import asyncio
import os
import platform
import signal
from asyncio import CancelledError, TimeoutError, subprocess
from dataclasses import dataclass
from time import perf_counter
from typing import Optional, Union

StrBytes = Union[str, bytes]
WINDOWS_HOST = platform.system() == "Windows"


@dataclass
class Result:
    return_code: Optional[int] = None
    stdout: Optional[bytes] = None
    stderr: Optional[bytes] = None
    time: Optional[float] = None
    os_error: Optional[str] = None
    killed: bool = False


async def arun(
    args: Union[list[StrBytes], StrBytes],
    timeout: Union[float, None] = None,
    env: Union[dict[str, StrBytes], None] = None,
):
    lbytes = isinstance(args, list) and any(isinstance(a, bytes) for a in args)

    if (isinstance(args, bytes) or lbytes) and WINDOWS_HOST:
        raise ValueError("Can't use bytes args on Windows hosts")

    try:
        if isinstance(args, list):
            p = await subprocess.create_subprocess_exec(
                *args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ | env if env else None,
            )
        else:
            p = await subprocess.create_subprocess_shell(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                env=os.environ | env if env else None,
            )
    except Exception as e:
        return Result(os_error=str(e))

    try:
        start = perf_counter()
        return_code = await asyncio.wait_for(p.wait(), timeout)
        time = perf_counter() - start
        stdout, stderr = await p.communicate()

        return Result(return_code, stdout, stderr, time)
    except (TimeoutError, CancelledError):
        if isinstance(args, list) or WINDOWS_HOST:
            p.kill()
        else:
            os.killpg(p.pid, signal.SIGKILL)

        stdout, stderr = await p.communicate()
        time = perf_counter() - start

        return Result(p.returncode, stdout, stderr, time, killed=True)


def run(
    args: Union[list[StrBytes], StrBytes],
    timeout: Union[int, None] = None,
    env: Union[dict[str, StrBytes], None] = None,
):
    return asyncio.run(arun(args, timeout, env))
