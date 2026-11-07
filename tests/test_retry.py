import json
import os
import time
from unittest.mock import AsyncMock, patch
import aio_pika
import pytest
from app.worker.retry import calculate_backoff_delay, handle_retry_or_dlq


def test_backoff_is_bounded_and_increases():
    assert [calculate_backoff_delay(i) for i in range(3)] == [2000, 4000, 8000]
    assert calculate_backoff_delay(1000) == 300000
    with pytest.raises(ValueError):
        calculate_backoff_delay(-1)


@pytest.mark.asyncio
async def test_retry_is_held_in_delay_queue_and_preserves_identity():
    channel = AsyncMock()
    payload = {'delivery_id': 'same-id', 'attempt': 0, 'payload': {'a': 1}}
    await handle_retry_or_dlq(channel, payload, 0)
    declaration = channel.declare_queue.call_args
    assert declaration.kwargs['arguments'] == {'x-message-ttl': 4000, 'x-dead-letter-exchange': '', 'x-dead-letter-routing-key': 'webhook_delivery_queue'}
    published = channel.default_exchange.publish.call_args
    assert published.kwargs['routing_key'] == declaration.args[0]
    assert published.kwargs['routing_key'] != 'webhook_delivery_queue'
    assert published.args[0].expiration is None
    assert json.loads(published.args[0].body)['delivery_id'] == 'same-id'
    assert payload['attempt'] == 0


@pytest.mark.asyncio
async def test_final_failure_goes_to_dlq():
    channel = AsyncMock()
    await handle_retry_or_dlq(channel, {'delivery_id': 'same-id'}, 4)
    assert channel.default_exchange.publish.call_args.kwargs['routing_key'] == 'webhook_dlq'
    assert json.loads(channel.default_exchange.publish.call_args.args[0].body)['attempt'] == 5


@pytest.mark.asyncio
async def test_publish_failure_propagates():
    channel = AsyncMock()
    channel.default_exchange.publish.side_effect = ConnectionError('broker disconnected')
    with pytest.raises(ConnectionError):
        await handle_retry_or_dlq(channel, {}, 0)


@pytest.mark.asyncio
async def test_real_broker_delays_delivery_and_routes_dlq():
    url = os.getenv('TEST_RABBITMQ_URL')
    if not url:
        pytest.skip('Set TEST_RABBITMQ_URL to an isolated RabbitMQ vhost')
    async with await aio_pika.connect_robust(url) as connection:
        channel = await connection.channel()
        queue = await channel.declare_queue('webhook_delivery_queue', durable=True)
        dlq = await channel.declare_queue('webhook_dlq', durable=True)
        await queue.purge()
        await dlq.purge()
        # Short TTL exercises the production queue topology without a slow suite.
        with patch('app.worker.retry.calculate_backoff_delay', return_value=600):
            started = time.monotonic()
            await handle_retry_or_dlq(channel, {'delivery_id': 'integration-id'}, 0)
            assert await queue.get(fail=False) is None
            async with queue.iterator(timeout=5) as iterator:
                message = await iterator.__anext__()
                assert time.monotonic() - started >= 0.5
                assert json.loads(message.body)['delivery_id'] == 'integration-id'
                await message.ack()
        await handle_retry_or_dlq(channel, {'delivery_id': 'integration-id'}, 4)
        message = await dlq.get(timeout=5)
        assert json.loads(message.body)['attempt'] == 5
        await message.ack()
        await channel.queue_delete('webhook_retry_1_600ms')
