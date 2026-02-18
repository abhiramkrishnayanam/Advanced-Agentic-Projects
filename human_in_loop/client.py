import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient

class WeatherTool:
    def __init__(self):
        self.client = None
        

    async def setup(self):
        """Initialize MCP client + Agent once."""
        self.client = MultiServerMCPClient(
            {
                "weather": {
                    "url": "http://localhost:8000/mcp",
                    "transport": "streamable_http",
                }
            }
        )
        tools = await self.client.get_tools()
        print("Available tools:", [t.name for t in tools])
        weather_tool = tools[0]
        result = await weather_tool.ainvoke({"city": "Bangalore", "date": "2025-08-28"})
        print("✅ Weather result:", result) 

if __name__ == "__main__":
    tool = WeatherTool()
    asyncio.run(tool.setup())