from typing import TypedDict, Annotated, Any, Dict
from langgraph.graph import StateGraph
import os
import warnings
from dotenv import load_dotenv
warnings.filterwarnings('ignore')
load_dotenv(override=True)


os.environ["LANGCHAIN_PROJECT"] = "Ticket Booking"

import requests
from datetime import datetime

class WeatherTool:
    def __init__(self):
        self.api_key = os.getenv("OPENWEATHER_API_KEY")
        self.base_url = "https://api.openweathermap.org/data/2.5/forecast"

    def get_weather(self, city: str, date: str) -> str:
        """
        Fetch weather forecast for a given city and date (within 8-day range).
        :param city: City name (str)
        :param date: Date string in 'YYYY-MM-DD' format
        :return: Weather description with temperature or error message
        """
        try:
            response = requests.get(
                self.base_url,
                params={"q": city, "appid": self.api_key, "units": "metric"}
            )
            response.raise_for_status()
            data = response.json()

            # Convert input date to datetime for comparison
            target_date = datetime.strptime(date, "%Y-%m-%d").date()

            # Check forecast list
            for entry in data["list"]:
                forecast_time = datetime.fromtimestamp(entry["dt"])
                if forecast_time.date() == target_date:
                    desc = entry["weather"][0]["description"].capitalize()
                    temp = entry["main"]["temp"]
                    return f"Weather in {city} on {date}: {desc}, {temp}°C"

            return f"No forecast available for {date}. Try another date within 5 days."

        except Exception as e:
            return f"Error fetching weather: {str(e)}"

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage


def get_weather_suggestion(weatherinfo: str):
    
    weather_info= weatherinfo
    # LLM for suggestion
    llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.0)

    system_message = SystemMessage(
    content=(
        "You are a reliable flight booking assistant. "
        "Provide clear, practical guidance on flying in the given weather. "
        "Highlight safety, risks, delays, and precautions in **maximum 4 concise bullet points**, "
        "including the city and date of travel. "
        "Ensure suggestions are actionable, trustworthy, and easy to follow."
        )
    )

    human_message = HumanMessage(
        content=(
            f"Weather forecast from OpenWeather API: {weather_info}. "
            f"First provide the city and date of travel. "
            f"Then give safety guidance for flying under these conditions, "
            f"covering risks, delays, and practical precautions in short, clear sentences."
        )
    )

     
    
    messages = [
    system_message,
    human_message
    ]
    
    response = llm.invoke(messages)
    return response.content

from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel
from typing import Optional

class FlightState(BaseModel):
    weather_info: Optional[str]=None
    safety_advice: Optional[str]=None
    user_confirmation: Optional[str]=None
    llm_output: Optional[str]=None
    City: Optional[str]=None
    Date: Optional[str]=None
    flight_name: Optional[str]=None
    destination: Optional[str]= None
    seat_preference: Optional[str] = "Any" # Window / Aisle / Middle
    departure: Optional[str]= None    
# class Passenger_details(BaseModel):
    passenger_name: Optional[str] = None
    Gender: Optional[str] = "Male"
    Age : Optional[int]= None
    passport_number: Optional[str] = None           # ID for international flights
    contact_number: Optional[str] =  None
    Chat_history:Optional[str] = None
    
from langgraph.pregel import Interrupt
from langgraph.types import interrupt, Command, Literal

def Human_confirmation(state: FlightState)->Command[Literal["final_confirmation"]]:
    print("Safety advice to user:\n", state.safety_advice)
    is_approved = interrupt({
        "question": "Do you want to confirm the booking?",
        "confirmation": None
    })

     # Normalize responses (yes, ok, book now → True | no, cancel → False)
    normalized = str(is_approved).strip().lower()
    confirm_words = {"yes", "ok", "book now", "confirm"}
    reject_words = {"no", "cancel", "not now"}

    if normalized in confirm_words:
        return Command(goto="get_details", update={"user_confirmation": "yes"})
    elif normalized in reject_words:
        return Command(goto="final_confirmation", update={"user_confirmation": "no"})
    else:
        # fallback → ask again
        return interrupt({"question": "Sorry, I didn’t get that. Confirm booking? (yes/no)"})
    

def get_details( flight: FlightState):
    flight.passenger_name = "Abhiram"
    flight.Age = 27
    flight.Gender = "Male"
    flight.contact_number = "989776786"
    
    flight.destination = "London"
    flight.flight_name = "Air India"
    flight.seat_preference = "Window"
    flight.departure = "10AM"
    
    return flight


from langchain_core.output_parsers import StrOutputParser
llm = ChatGroq(model="gemma2-9b-it")
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
def final_llm_response(state: FlightState):
    user_conf = state.user_confirmation.strip().lower()

    if user_conf:
        prompt = f"""
You are a helpful flight ticket booking assistant.

User reply: {{user_conf}}

If the user replies "Yes":
- First, greet the passenger with a welcome message to their airline. Example: 
  "Welcome aboard {state.flight_name} Airlines! We're excited to serve you."
- Then, generate a dummy flight ticket in a clean and professional ticket format like this:

--------------------------------------------------
                ✈ Flight Ticket ✈
--------------------------------------------------
 Passenger Name : {state.passenger_name}
 Age            : {state.Age}
 Gender         : {state.Gender}
 Contact Number : {state.contact_number}
--------------------------------------------------
 Airline        : {state.flight_name}
 Departure      : {state.departure}
 From           : {state.City}
 To             : {state.destination}
 Date           : {state.Date}
 Seat Preference: {state.seat_preference}
--------------------------------------------------
   Wishing you a safe and pleasant journey! ✈
--------------------------------------------------

If the user replies "No":
Respond politely with: 
"Thank you for using! See you again."
"""

    
    # Call LLM
    result = llm.invoke(prompt)

    # force string
    state.llm_output = str(result)  

    # OR, if result has .content (LLM message object)
    state.llm_output = result.content if hasattr(result, "content") else str(result)

    return state

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.store.base import BaseStore

from trustcall import create_extractor
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from typing import List
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

across_thread_memory = InMemoryStore()
within_thread_memory = MemorySaver()

class FlightRecord(BaseModel):
    date: str = Field(description="Flight date in YYYY-MM-DD format")
    airline: str = Field(description="Airline name")
    origin: str = Field(description="Departure city")
    destination: str = Field(description="Arrival city")
    seat: str = Field(description="Seat preference")
    departure_time: str = Field(description="Scheduled departure time")
    summary: str = Field(description="Concise human-readable ticket summary")

class UserProfile(BaseModel):
    user_name: str = Field(description="The user's preferred name")
    flight_history: List[FlightRecord] = Field(
        default_factory=list,
        description="List of all past flight tickets with structured details"
    )

# Initialize base LLM
model =  ChatGroq(model="llama-3.1-8b-instant", temperature= 0.0)

# TrustCall extractor
trustcall_extractor = create_extractor(
    model,
    tools=[UserProfile],
    tool_choice="UserProfile"
)

MODEL_SYSTEM_MESSAGE = """You are a flight booking assistant with memory that provides information about the user. 
If you have memory for this user, use it to personalize responses (e.g., greet them by name, recall seat preference, or reference past flights). 
Here is the memory (it may be empty): {memory}"""

TRUSTCALL_INSTRUCTION = """Create or update the user profile memory (JSON doc) to incorporate information from the following conversation.
The memory should follow this schema:
- user_name: The user's preferred name
- flight_history: A list of FlightRecord objects, where each record contains:
  (date, airline, origin, destination, seat, departure_time, summary)

Rules:
- Always preserve existing memory.
- If a new flight is mentioned, append it to flight_history as a new record.
- If a flight with the same date already exists, update its details instead of duplicating.
- Keep all data consistent and structured."""



def write_memory(state: FlightState, config: RunnableConfig, store: BaseStore):
    """Reflect on the booking conversation and save memory to the store."""

    # Get user id from config
    user_id = config["configurable"]["user_id"]

    # Load existing memory
    namespace = ("memory", user_id)
    existing_memory = store.get(namespace, "flight_history")

    # Prepare existing profile if any
    existing_profile = {"UserProfile": existing_memory.value} if existing_memory else None

    # Invoke the extractor
    result = trustcall_extractor.invoke(
        {"messages": [SystemMessage(content=TRUSTCALL_INSTRUCTION)]+state["messages"], "existing": existing_profile})
    
    # Convert response into dict (JSON-like)
    updated_profile = result.responses[0].model_dump()

    # Save updated profile back to store
    key = "flight_history"
    store.put(namespace, key, updated_profile)

    return state

from tabulate import tabulate

def call_memory(state: FlightState, config: RunnableConfig, store: BaseStore):
    """Load flight booking history from memory and return it as formatted output."""

    # Get user ID
    user_id = config["configurable"]["user_id"]

    # Retrieve memory
    namespace = ("memory", user_id)
    existing_memory = store.get(namespace, "flight_history")

    if existing_memory and existing_memory.value:
        memory_value = existing_memory.value

        # Ensure we have a list of dicts
        if isinstance(memory_value, dict):
            history_list = [memory_value]  # wrap single dict in a list
        elif isinstance(memory_value, list):
            history_list = memory_value
        else:
            history_list = []

        # Generate table
        table_data = [
            [i+1,
            entry.get("Date", "Unknown"),
            entry.get("destination", "Unknown"),
            entry.get("flight_name", "Unknown"),
            entry.get("passenger_name", "Unknown")]
            for i, entry in enumerate(history_list)
        ]
        headers = ["#", "Date", "Destination", "Flight", "Passenger"]
        formatted_history = tabulate(table_data, headers=headers, tablefmt="pretty")
    else:
        formatted_history = "No past flight history found."

    # Format the memory in the system prompt
    system_msg = MODEL_SYSTEM_MESSAGE.format(memory=formatted_history)

    # Respond using memory as well as the chat history
    response = llm.invoke([SystemMessage(content=system_msg)]+state.llm_output)
    
    return {"Chat_history": response}
    # 🔹 Print directly in proper format
    # print(state.Chat_history)

    # return state

def Weather_prediction(state: FlightState):
    date=state.Date 
    city=state.City
    weather=WeatherTool()

    state.weather_info= weather.get_weather(city, date)
    return state

def Suggetion(state: FlightState):
    weather_info=state.weather_info
    state.safety_advice= get_weather_suggestion(weather_info)
    return state

from langgraph.checkpoint.memory import MemorySaver

def history_condition(state):
    user_input = input("\n🤔 Do you want to see your flight history? (yes/no) ")
    if user_input.lower() == "yes":
        return "call_memory"
    else:
        return "end"


graph = StateGraph(FlightState)

graph.add_node("Weather_prediction",Weather_prediction)
graph.add_node("Suggetion",Suggetion)
graph.add_node("Human_confirmation", Human_confirmation)
graph.add_node("final_confirmation",final_llm_response )
graph.add_node("get_details", get_details)
graph.add_node("write_memory", write_memory)
graph.add_node("call_memory", call_memory)



graph.add_edge(START, "Weather_prediction")
graph.add_edge("Weather_prediction", "Suggetion")
graph.add_edge("Suggetion", "Human_confirmation")
graph.add_edge("Human_confirmation", "get_details")
graph.add_edge("get_details","final_confirmation")
graph.add_edge("final_confirmation","write_memory")

graph.add_conditional_edges(
    "write_memory",
    history_condition,   # function returning node name
    {
        "call_memory": "call_memory",
        "end": END,
    },
)

memory_store = MemorySaver()
graph_final = graph.compile(
    checkpointer=within_thread_memory,
    store=across_thread_memory
)

for event in graph_final.stream(
    {"City": "Bangalore", "Date": "2025-08-27"},
    config={"configurable": {"thread_id": "1", "user_id": "user1"}},
    stream_mode= "updates"
    ):
    print(event)
    print("\n")

# Continue the graph execution
for event in graph_final.stream(
    Command(resume="yes"),
    config={"configurable": {"thread_id": "1", "user_id": "user1"}},
    stream_mode="updates",
):
    print(event)
    print("\n")
   