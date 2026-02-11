import asyncio
import pprint

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main() -> None:
    async with streamable_http_client("http://127.0.0.1:8000/mcp") as (
        read,
        write,
        session_id,
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()

            list_tools_result = await session.list_tools()
            print("list_tools() raw:")
            pprint.pprint(list_tools_result)
            print("type(list_tools_result)=", type(list_tools_result))

            tools = getattr(list_tools_result, "tools", None)
            if tools is None:
                print("Unexpected: list_tools_result.tools is None")
            else:
                print("Available tools:", [t.name for t in tools])

            target_handle = "bsky.app"
            print(f"\nFetching profile for: {target_handle}")
            call_result = await session.call_tool("bsky_get_profile", {"handle": target_handle})

            print("call_tool() raw:")
            pprint.pprint(call_result)
            print("type(call_result)=", type(call_result))

            content = getattr(call_result, "content", None)
            if not content:
                print("No content in CallToolResult")
                return

            first = content[0]
            text = getattr(first, "text", None)
            if text is None:
                print("Unexpected content item (no .text):")
                pprint.pprint(first)
                return

            print("Result Profile (text):")
            print(text)


if __name__ == "__main__":
    asyncio.run(main())
