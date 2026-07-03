from sibyl.ingestion.adapters.dedup import is_duplicate_delivery


async def test_first_delivery_is_not_a_duplicate(redis_client):
    assert await is_duplicate_delivery(redis_client, "delivery-1") is False


async def test_repeated_delivery_is_a_duplicate(redis_client):
    await is_duplicate_delivery(redis_client, "delivery-2")

    assert await is_duplicate_delivery(redis_client, "delivery-2") is True


async def test_different_deliveries_are_independent(redis_client):
    await is_duplicate_delivery(redis_client, "delivery-3")

    assert await is_duplicate_delivery(redis_client, "delivery-4") is False
