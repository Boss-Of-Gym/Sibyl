from redis.asyncio import Redis

DEDUP_KEY_PREFIX = "dedup:webhook:"
DEDUP_TTL_SECONDS = 600


async def is_duplicate_delivery(redis: Redis, github_delivery_id: str) -> bool:
    key = f"{DEDUP_KEY_PREFIX}{github_delivery_id}"
    was_set = await redis.set(key, "1", nx=True, ex=DEDUP_TTL_SECONDS)
    return not was_set
