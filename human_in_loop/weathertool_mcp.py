import os
import httpx
from datetime import datetime
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

mcp = FastMCP("Weather")
load_dotenv(override=True)

@mcp.tool()
async def get_weather(city: str, date: str) -> str:
    """
    Fetch weather forecast for a given city and date (within 5-day range).
    :param city: City name
    :param date: Date in 'YYYY-MM-DD'
    """
    try:
        api_key = os.getenv("OPENWEATHER_API_KEY")
        if not api_key:
            return "Error: OPENWEATHER_API_KEY is not set."
        
        base_url = "https://api.openweathermap.org/data/2.5/forecast"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                base_url,
                params={"q": city, "appid": api_key, "units": "metric"}
            )
            
            response.raise_for_status()
            data = response.json()
        
        # Parse target date
        target_date = datetime.strptime(date, "%Y-%m-%d").date()

        #Look for matching forecast
        for entry in data["list"]:
            forecast_time = datetime.fromtimestamp(entry["dt"])

            if forecast_time.date() == target_date:
                desc = entry["weather"][0]["description"].capitalize()
                temp = entry["main"]["temp"]
                return f"Weather in {city} on {date}: {desc}, {temp}°C"

        return f"No forecast available for {date}. Try another date within 5 days."

    except Exception as e:
        return f"Error fetching weather: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
   