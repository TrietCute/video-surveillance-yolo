import asyncio
from collections import namedtuple
from queue import Queue
from threading import Thread

CameraTask = namedtuple("CameraTask", ["thread", "queue"])

registry: dict[str, CameraTask] = {}