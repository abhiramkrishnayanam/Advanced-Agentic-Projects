from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.messages import AnyMessage
import json
import re
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.graph.message import add_messages
from typing import Annotated
from langgraph.store.base import BaseStore
from trustcall import create_extractor
from typing import Optional
from agent_state import AgentState
from langchain_groq import ChatGroq
import warnings
from dotenv import load_dotenv
warnings.filterwarnings('ignore')
load_dotenv(override=True)

# Initialize the model (using Groq instead of OpenAI as in your original code)
model = ChatGroq(model="openai/gpt-oss-20b", temperature=0)

# Define the schema for storing email addresses
class EmailContacts(BaseModel):
    """A tool to store and manage email addresses for user contacts."""
    email_addresses: dict = Field(
        description="A dictionary mapping contact names to their corresponding email addresses."
    )

# Create the extractor with 'auto' tool_choice
trustcall_extractor = create_extractor(
    model,
    tools=[EmailContacts],
    tool_choice="auto",
    enable_inserts=True,
)

# Instruction for the model when extracting information
TRUSTCALL_INSTRUCTION = """
You are a specialized tool designed to extract email addresses and their corresponding contact names. Your output must be a valid JSON object matching the `EmailContacts` schema.

**Instructions:**
- If a contact and email are mentioned, add or update the entry in the `email_addresses` dictionary.
- If the email address for an existing contact changes, you must overwrite the old email with the new one.

**Examples:**
1.  **New Contact:**
    User: "My friend Alice's email is alice@gmail.com."
    Output:
    {
        "email_addresses": {
            "alice": "alice@gmail.com"
        }
    }

2.  **Update Existing Contact:**
    User: "Actually, Alice's new email is alice.smith@company.com."
    Output:
    {
        "email_addresses": {
            "alice": "alice.smith@company.com"
        }
    }

If no email address is mentioned, return an empty dictionary. Do not include any other text.
"""
def send_email_draft(state: AgentState, config: RunnableConfig, store: BaseStore):
    """Loads email contacts from memory and drafts an email."""
    user_id = config["configurable"]["user_id"]
    namespace = ("memory", user_id)
    existing_memory = store.get(namespace, "email_book")

    email_book = existing_memory.value.get('email_addresses', {}) if existing_memory and existing_memory.value else {}
    formatted_email_book = json.dumps(email_book, indent=2)


    
    system_msg = f"""
    You are an intelligent email assistant with memory. The following is the user's saved email contacts:

    {formatted_email_book}

    If the user asks to send an email to a contact, look up the contact in the email book.
    - If found, generate a draft email in JSON format with "to", "subject", and "body".
    - If not found, respond by asking the user for the contact's email address.
    
    
    Do not include any explanation or extra text. Remember Strictly the output must be valid JSON.
    """
    
    # Collect all messages
    messages = [SystemMessage(content=system_msg), HumanMessage(content=state.query)]

    # If state.messages exists, extend
    if hasattr(state, "messages") and state.messages:
        messages.extend(state.messages)

    # Now invoke model with proper list of Message objects
    response = model.invoke(messages)
    
    # Step 1: strip whitespace
    raw = response.content.strip()

    # Step 2: extract JSON object using regex
    match = re.search(r"{.*}", raw, re.DOTALL)
    if match:
        raw_json = match.group()
        try:
            email_objects = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from model output: {raw_json}") from e
    else:
        raise ValueError(f"No JSON found in model output: {raw}")

    state.to = email_objects.get("to")
    state.subject = email_objects.get("subject")
    state.body = email_objects.get("body")
    return state

def update_memory(state: AgentState, config: RunnableConfig, store: BaseStore):
    """Reflects on the chat history and saves new email contacts to the store."""
    user_id = config["configurable"]["user_id"]
    namespace = ("memory", user_id)
    existing_memory = store.get(namespace, "email_book")
    existing_profile = {"EmailContacts": existing_memory.value} if existing_memory and existing_memory.value else None
    
    result = trustcall_extractor.invoke({
    "messages": [SystemMessage(content=TRUSTCALL_INSTRUCTION), HumanMessage(content=state.query)],
    "existing": existing_profile
    })
    if result.get("responses") and len(result["responses"]) > 0:
        updated_profile = result["responses"][0].model_dump()
        key = "email_book"
        store.put(namespace, key, updated_profile)

# Define the graph
builder = StateGraph(AgentState)
builder.add_node("send_email_draft", send_email_draft)
builder.add_node("update_memory", update_memory)

# Add edges in sequence
builder.add_edge(START, "send_email_draft")
builder.add_edge("send_email_draft", "update_memory")
builder.add_edge("update_memory", END)

# Use MemorySaver for in-memory persistence
# In-memory store for persistent storage (across invocations)
across_thread_memory = InMemoryStore()

# Short-term checkpointer
within_thread_memory = MemorySaver()

# Compile the graph
draft_graph = builder.compile(
    checkpointer=within_thread_memory,
    store=across_thread_memory
)




#Testing 

# if __name__ == "__main__":
#     state3= AgentState(query="Send an email to Abhiram. To inform him about tomorrows meeting and there after lunch")
#     config = {"configurable": {"thread_id": "1", "user_id": "user_123"}}
#     response = draft_graph.invoke(state3,  config=config)
#     print(response)