import asyncio
from livekit.api import LiveKitAPI, CreateAgentDispatchRequest

async def main():
    async with LiveKitAPI(
        url="ws://localhost:7880",
        api_key="devkey",
        api_secret="secret",
    ) as api:
        dispatch = await api.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(
                agent_name="armenian-bank-agent",
                room="test-room",
            )
        )
        print(f"Dispatched! {dispatch}")

asyncio.run(main())