import os
import unittest

from unittest import mock

import pytest

from prometheus_client import REGISTRY

try:
    import redis
except ImportError:
    raise unittest.SkipTest("redis-py is not installed")
else:
    del redis
from redis.exceptions import ConnectionError

from baseplate.lib.config import ConfigurationError
from baseplate.clients.redis import pool_from_config
from baseplate.clients.redis import ACTIVE_REQUESTS
from baseplate.clients.redis import REQUESTS_TOTAL
from baseplate.clients.redis import LATENCY_SECONDS
from baseplate.clients.redis import MonitoredRedisConnection


class DummyConnection:
    description_format = "DummyConnection<>"

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.pid = os.getpid()

    def connect(self):
        pass

    def can_read(self):
        return False

    def send_command(self, command):
        pass

    def read_response(self):
        pass


class TestMonitoredRedisConnection:
    def setup(self):
        ACTIVE_REQUESTS.clear()
        REQUESTS_TOTAL.clear()
        LATENCY_SECONDS.clear()

    @pytest.fixture
    def app_config(self):
        yield {
            "redis.url": "redis://localhost:1234/0",
        }

    @pytest.fixture
    def expected_labels(self):
        yield {
            "redis_client_name": "test_client",
            "redis_type": "standalone",
            "redis_command": "some_command",
            "redis_database": "0",
        }

    @pytest.fixture
    def connection(self):
        yield {"connection_class": DummyConnection}

    @pytest.fixture
    def connection_pool(self, app_config, connection):
        yield pool_from_config(
            app_config=app_config, prefix="redis.", client_name="test_client", **connection
        )

    @pytest.fixture
    def context(self):
        yield mock.MagicMock()

    @pytest.fixture
    def span(self):
        yield mock.MagicMock()

    @pytest.fixture
    def monitored_redis_connection(self, span, connection_pool):
        yield MonitoredRedisConnection("redis_context_name", span, connection_pool)

    def test_execute_command_exc_redis_err(
        self, monitored_redis_connection, expected_labels, app_config
    ):
        monitored_redis_connection.connection_pool = pool_from_config(
            app_config=app_config, client_name="test_client"
        )
        with pytest.raises(ConnectionError):  # ConnectionError inherits from RedisError
            monitored_redis_connection.execute_command("some_command")
        assert REGISTRY.get_sample_value(f"{ACTIVE_REQUESTS._name}", expected_labels) == 0
        expected_labels["redis_success"] = "false"
        assert (
            REGISTRY.get_sample_value(
                f"{LATENCY_SECONDS._name}_bucket", {**expected_labels, **{"le": "+Inf"}}
            )
            == 1
        )
        assert REGISTRY.get_sample_value(f"{REQUESTS_TOTAL._name}_total", expected_labels) == 1

    def test_execute_command_empty_client_name(
        self, monitored_redis_connection, expected_labels, app_config
    ):
        monitored_redis_connection.connection_pool = pool_from_config(
            app_config=app_config, client_name=""
        )
        expected_labels.pop("redis_client_name")

        with pytest.raises(ConnectionError):  # ConnectionError inherits from RedisError
            monitored_redis_connection.execute_command("some_command")
        assert REGISTRY.get_sample_value(f"{REQUESTS_TOTAL._name}_total", expected_labels)

    def test_execute_command(self, monitored_redis_connection, expected_labels):
        monitored_redis_connection.execute_command("some_command")
        # assert [i for i in REGISTRY.collect()] == ""
        assert REGISTRY.get_sample_value(f"{ACTIVE_REQUESTS._name}", expected_labels) == 0
        expected_labels["redis_success"] = "true"
        assert (
            REGISTRY.get_sample_value(
                f"{LATENCY_SECONDS._name}_bucket", {**expected_labels, **{"le": "+Inf"}}
            )
            == 1
        )
        assert REGISTRY.get_sample_value(f"{REQUESTS_TOTAL._name}_total", expected_labels) == 1


class TestPoolFromConfig:
    def test_empty_config(self):
        with pytest.raises(ConfigurationError):
            pool_from_config({})

    def test_basic_url(self):
        pool = pool_from_config({"redis.url": "redis://localhost:1234/0"})

        assert pool.connection_kwargs["host"] == "localhost"
        assert pool.connection_kwargs["port"] == 1234
        assert pool.connection_kwargs["db"] == 0

    def test_timeouts(self):
        pool = pool_from_config(
            {
                "redis.url": "redis://localhost:1234/0",
                "redis.socket_timeout": "30 seconds",
                "redis.socket_connect_timeout": "300 milliseconds",
            }
        )

        assert pool.connection_kwargs["socket_timeout"] == 30
        assert pool.connection_kwargs["socket_connect_timeout"] == 0.3

    def test_kwargs_passthrough(self):
        pool = pool_from_config({"redis.url": "redis://localhost:1234/0"}, example="present")

        assert pool.connection_kwargs["example"] == "present"

    def test_alternate_prefix(self):
        pool_from_config({"noodle.url": "redis://localhost:1234/0"}, prefix="noodle.")
