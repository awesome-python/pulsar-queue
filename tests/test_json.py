"""Tests task execution with JSON serialiser"""
import unittest

from tests import app


class TestMsgPackQueue(app.TaskQueueApp, unittest.TestCase):
    message_serializer = 'json'
