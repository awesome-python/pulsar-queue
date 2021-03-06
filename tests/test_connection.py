"""Tests connection errors"""
import unittest
from asyncio import Future

from pulsar import send
from pulsar.utils.string import random_string

from pq import api


class Tester:

    def __init__(self):
        self.end = Future()

    def __call__(self, *args, **kwargs):
        if not self.end.done():
            self.end.set_result((args, kwargs))


class TestConnectionDrop(unittest.TestCase):
    app = None

    async def setUp(self):
        self.app = api.TaskApp(
            name='connection_%s' % random_string(),
            config='tests.config',
            workers=0
        )
        await self.app.start()
        self.backend = self.app._backend

    async def tearDown(self):
        if self.app:
            await send('arbiter', 'kill_actor', self.app.name)

    async def test_fail_get_task(self):
        original, warning, critical = self._patch(
            self.backend.broker, 'get_task')
        args, kw = await critical.end
        self.assertEqual(len(args), 3)
        self.assertEqual(args[1], self.backend.broker)
        self.assertEqual(args[2], 2)
        critical.end = Future()
        args, kw = await critical.end
        self.assertEqual(args[1], self.backend.broker)
        self.assertEqual(args[2], 2.25)

    async def test_fail_publish(self):
        original, warning, critical = self._patch(
            self.backend.pubsub._pubsub, 'publish')
        task = self.backend.queue_task('addition', a=1, b=2)
        args, kw = await critical.end
        self.assertEqual(len(args), 3)
        self.assertEqual(args[1], self.backend.pubsub)
        task.cancel()

    async def test_fail_subscribe(self):
        await self.backend.pubsub.close()
        original, warning, critical = self._patch(
            self.backend.pubsub._pubsub, 'psubscribe')
        await self.backend.pubsub.start()
        args, kw = await critical.end
        self.assertEqual(len(args), 4)
        self.assertEqual(args[1], self.backend.pubsub)
        self.assertEqual(args[3], 2)
        critical.end = Future()
        args, kw = await critical.end
        self.assertEqual(len(args), 4)
        self.assertEqual(args[1], self.backend.pubsub)
        self.assertEqual(args[3], 2.25)
        self.backend.pubsub._pubsub.psubscribe = original
        args, kw = await warning.end
        self.assertEqual(len(args), 3)
        self.assertEqual(args[1], self.backend.pubsub)
        self.assertEqual(args[2], '%s_*' % self.app.name)

    def _log_error(self, coro, *args, **kwargs):
        coro.switch((args, kwargs))

    def _connection_error(self, *args, **kwargs):
        raise ConnectionRefusedError

    def _patch(self, obj, method):
        original = getattr(obj, method)
        setattr(obj, method, self._connection_error)
        critical = Tester()
        warning = Tester()
        self.backend.logger.critical = critical
        self.backend.logger.warning = warning
        return original, warning, critical
