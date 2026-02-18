import re
import json
import warnings
from dotenv import load_dotenv
warnings.filterwarnings('ignore')
load_dotenv(override=True)

from langchain_groq import ChatGroq
from langgraph.types import Command, interrupt
from langchain.schema import SystemMessage
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables.config import RunnableConfig
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.store.base import BaseStore

from agent_state import AgentState
from summarize import generate_thread_summary_node
from delete import select_and_trash_message, trash_message
from count import get_email_count_today
from draft import trustcall_extractor, TRUSTCALL_INSTRUCTION
from sender import send_email, get_gmail_service
from rag import qa_generator

llm= ChatGroq(model="openai/gpt-oss-20b", temperature= 0)


# client = AzureOpenAI(
#     api_key=os.environ["AZURE_OPENAI_KEY"],
#     api_version="2024-02-15-preview",
#     azure_endpoint=os.environ["AZURE_OPENAI_BASE"]
# )


# -----------------------------
# Memory persistence utility functions
# -----------------------------
MEMORY_FILE = "email_memory.json"


def load_memory(store: InMemoryStore, user_id="me"):
    """Load memory from JSON file into InMemoryStore"""
    try:
        with open(MEMORY_FILE, "r") as f:
            content = f.read().strip()
            if content:  # Only load if file is not empty
                data = json.loads(content)
                store.put(("memory", user_id), "email_book", data)
                print("✅ Memory loaded from file.")
            else:
                print("⚠️ Memory file is empty. Starting fresh.")
    except FileNotFoundError:
        print("⚠️ No previous memory found. Starting fresh.")
    except json.JSONDecodeError:
        print("⚠️ Memory file is corrupted. Starting fresh.")


def save_memory(store: InMemoryStore, user_id="me"):
    """Save memory from InMemoryStore to JSON file"""
    memory_data = store.get(("memory", user_id), "email_book")
    if memory_data:
        with open(MEMORY_FILE, "w") as f:
            json.dump(memory_data.value, f)
            print("✅ Memory saved to file.")

##################################################################

def router_node(state: AgentState) -> Command:
    query = state.query

    prompt = f"""
You are an intelligent email assistant for a Gmail support agent.
Your job is to decide which action node the system should route to,
based on the user's natural language query.

Available nodes:
- summarize_thread_node → summarize emails, threads, or attachments.
- delete_email_node → delete one or more emails or threads.
- reply_from_kb_node → reply to a customer email using the knowledge base.
- analytics_node → queries like count emails, emails sent today, responded emails.
- send_email_node → send an email to a recipient.

Rules:
- Always pick exactly one node.
- Output strictly valid JSON:
  {{
    "next_node": "<one of: summarize_thread_node, delete_email_node, reply_from_kb_node, analytics_node, send_email_node>"
  }}

User query: "{query}"
"""

    resp = llm.invoke(prompt)
    raw_output = resp.content.strip()
    try:
        parsed = json.loads(raw_output)
        next_node = parsed.get("next_node", "")
    except json.JSONDecodeError:
        return Command(goto=END)
    state.next_node = next_node

    # ---- Router logic ----
    if next_node == "summarize_thread_node":
        return Command(goto="summary_node")
    elif next_node == "delete_email_node":
        return Command(goto="delete_node")
    elif next_node == "reply_from_kb_node":
        return Command(goto="qa_node")
    elif next_node == "analytics_node":
        return Command(goto="count_node") 
    elif next_node == "send_email_node":
        return Command(goto="draft_email_node") 
    else:
        return Command(goto=END)

##################################################################

def get_summary_node(state: AgentState):
    query = state.query
    user_id = state.user_id

    prompt = """You are a structured information extraction tool designed to analyze user queries related to emails and extract exactly one piece of information from the following three categories:

from: [extracted sender email-id]
    
to: [extracted recipient email-id]

subject: [extracted subject]

⚠️ The extracted email address must be in the correct email format (e.g., alice@example.com).  
⚠️ Do not add any explanations, additional text, or conversational language.  
⚠️ If an email-id is not explicitly mentioned but a name is, return the name in place of the email-id.  
⚠️ If none of the fields are clearly present, respond with either a subject: [some subject] or to: [some recipient] line, based on the most relevant information you can confidently extract.

Here is the user query:
{query}
"""

    llm_prompt = prompt.format(query=query.strip())

    # Assume `llm.invoke` accepts a list of messages
    response = llm.invoke([
        SystemMessage(content=llm_prompt)
    ])

    # Ensure it's a string
    if hasattr(response, "content"):
        response_text = response.content
    else:
        response_text = str(response)
    
    # Generate the thread summary
    state.summary = generate_thread_summary_node(user_id, response_text)

    return state

##################################################################

def delete_node(state: AgentState, config: RunnableConfig, store: BaseStore):
    print("delete_node")
    query=state.query

    """Loads email contacts from memory and drafts an email."""
    user_id = config["configurable"]["user_id"]
    namespace = ("memory", user_id)
    existing_memory = store.get(namespace, "email_book")

    email_book = existing_memory.value.get('email_addresses', {}) if existing_memory and existing_memory.value else {}
    formatted_email_book = json.dumps(email_book, indent=2)
    
    prompt = """
You are a structured email information extraction tool.


---Here is the saved EMAIL BOOK (do NOT invent any address; only use addresses that appear here) ---
{formatted_email_book}

Your task is to analyze the user query and extract exactly one piece of information from the following categories:


to: [recipient email-id or name]
subject: [subject]

⚠️ Rules:
- If the query contains a new email-id, use that email-id (overwrite memory).
- If the query only has a name, look up the email-id from the saved email book.
- If neither name nor email-id can be found, return: 
  "⚠️ No recipient email-id found. Please provide a valid email-id in your query."
- Always return the result in the exact structured format above, no explanations.
- Email address must be in correct format (e.g., alice@example.com).

Here is the user query:
{query}
"""

    llm_prompt = prompt.format(query=query.strip(), formatted_email_book=formatted_email_book)

    # Assume `llm.invoke` accepts a list of messages
    response = llm.invoke([
        SystemMessage(content=llm_prompt)
    ])

    # If response is AIMessage, extract `.content`
    state.query_dlt = response.content if hasattr(response, "content") else str(response)
    if state.query_dlt == "⚠️ No recipient email-id found. Please provide a valid email-id in your query.":
        return Command(goto=END)
    # state.deleted= select_and_trash_message(user_id, query_text)
    return state


def approval_delete_node(state: AgentState) -> Command:
    print("✋ Waiting for human approval to delete email...")

    # Ask user explicitly
    approval = interrupt({
        "question": f"Do you want to delete this email?\n\nQuery: {state.query}\nCandidate: {state.deleted}\n\n(yes/no)",
        "confirmation": None
    })

    normalized = str(approval).strip().lower()
    confirm_words = {"yes", "ok", "delete", "confirm"}
    reject_words = {"no", "cancel", "not now"}

    if normalized in confirm_words:
        return Command(goto="execute_delete_node")  # proceed with deletion
    elif normalized in reject_words:
        return Command(goto=END)                    # stop without deleting
    else:
        # If unclear → ask again
        return interrupt({"question": "Sorry, I didn’t get that. Delete email? (yes/no)"})

def execute_delete_node(state: AgentState):
    print("✅ Executing delete after approval...")
    user_id = state.user_id
    query_dlt = state.query_dlt  # structured extracted query from delete_node

    # Step 1: find the message
    result = select_and_trash_message(user_id, query_dlt)
    if result["status"] != "found":
        state.deleted = result
        return state

    # Step 2: trash the message
    trash_result = trash_message(user_id, result["message_id"])
    state.deleted = trash_result
    return  Command(goto=END)

##################################################################

def count_node(state: AgentState):
    print("count_node")
    state.count= get_email_count_today()
    return state

##################################################################

def draft_email_node(state: AgentState, config: RunnableConfig, store: BaseStore):
    """Loads email contacts from memory and drafts an email."""
    user_id = config["configurable"]["user_id"]
    namespace = ("memory", user_id)
    existing_memory = store.get(namespace, "email_book")

    email_book = existing_memory.value.get('email_addresses', {}) if existing_memory and existing_memory.value else {}
    formatted_email_book = json.dumps(email_book, indent=2)

    print("generating email draft")
    
    system_msg = f"""
You are an intelligent email assistant with memory. The following is the user's saved email contacts:

{formatted_email_book}

Rules for drafting emails:
- If the user asks to send an email to a contact:
  • If the user provides a new email address for that person, always use the new email from the user (overwrite memory).
  • If the user only provides a name (without an email), look it up in the saved email book.
- Generate a draft email in JSON format with "to", "subject", and "body".
- If the model generates a sign-off phrase (like "Best,", "Thanks,", "Regards,"), do not remove it — just ensure that it is immediately followed by the name "Abhiram".
- Do not include any explanation or extra text. The output must be valid JSON only.
"""
    
    # Collect all messages
    messages = [SystemMessage(content=system_msg), HumanMessage(content=state.query)]

    # If state.messages exists, extend
    if hasattr(state, "messages") and state.messages:
        messages.extend(state.messages)

    # Now invoke model with proper list of Message objects
    response = llm.invoke(messages)
    
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


def approval_send_node(state: AgentState) -> Command:
    print("✋ Waiting for human approval to send email...")

    # Ask user explicitly
    approval = interrupt({
        "question": f"Do you want to send this email?\n\nTo: {state.to}\nSubject: {state.subject}\n\n{state.body}\n\n(yes/no)",
        "confirmation": None
    })

    normalized = str(approval).strip().lower()
    confirm_words = {"yes", "ok", "send", "confirm"}
    reject_words = {"no", "cancel", "not now"}

    if normalized in confirm_words:
        return Command(goto="update_memory_node")   # proceed in pipeline
    elif normalized in reject_words:
        return Command(goto=END)                   # stop without sending
    else:
        # If unclear → ask again
        return interrupt({"question": "Sorry, I didn’t get that. Send email? (yes/no)"})

def update_memory(state: AgentState, config: RunnableConfig, store: BaseStore):
    """Reflects on the chat history and saves new email contacts to the store."""
    user_id = config["configurable"]["user_id"]
    namespace = ("memory", user_id)
    existing_memory = store.get(namespace, "email_book")
    existing_profile = {"EmailContacts": existing_memory.value} if existing_memory and existing_memory.value else None
    print("memory updation")

    result = trustcall_extractor.invoke({
    "messages": [SystemMessage(content=TRUSTCALL_INSTRUCTION), HumanMessage(content=state.query)],
    "existing": existing_profile
    })
    if result.get("responses") and len(result["responses"]) > 0:
        updated_profile = result["responses"][0].model_dump()
        key = "email_book"
        store.put(namespace, key, updated_profile)

    return state


def sender_node(state: AgentState):
    print("sender node") 
    gmail_service = get_gmail_service()

    if gmail_service:    
        send_email(state.to, state.subject, state.body)
        print(f"📧 Email sent to {state.to}")
    else:
        state.gmail_service_warning = "⚠️ Failed to get Gmail service. Check credentials and network connection."
    return state

##################################################################

def qa_node(state: AgentState):
    query = state.query
    print("qa_node")
    parsed = qa_generator(query)
    
    if parsed["flag"]:
        # no answer, push to flagged state
        state.flagged_messages.append(query)
        state.answers= "❓ This query requires human support."
    else:
        # only return the answer string
        state.answers= parsed["answer"]
    return state


graph = StateGraph(AgentState)
graph.add_node("router_node", router_node)
graph.add_node("sender_node", sender_node)
graph.add_node("approval_send_node", approval_send_node)
graph.add_node("summary_node", get_summary_node)
graph.add_node("qa_node", qa_node)
graph.add_node("delete_node", delete_node)
graph.add_node("approval_delete_node", approval_delete_node)
graph.add_node("execute_delete_node",execute_delete_node )
graph.add_node("count_node", count_node)
graph.add_node("draft_email_node", draft_email_node)
graph.add_node("update_memory_node", update_memory)

graph.add_edge(START,"router_node")
graph.add_edge("draft_email_node", "approval_send_node")
graph.add_edge("approval_send_node", "update_memory_node")
graph.add_edge("update_memory_node", "sender_node")
graph.add_edge("sender_node",END)
graph.add_edge("summary_node",END)
graph.add_edge("qa_node",END)
graph.add_edge("delete_node", "approval_delete_node")
graph.add_edge("approval_delete_node", "execute_delete_node")
graph.add_edge("execute_delete_node", END)
graph.add_edge("count_node",END)

across_thread_memory = InMemoryStore()

within_thread_memory = MemorySaver()

agent_graph= graph.compile(
    checkpointer=within_thread_memory,
    store=across_thread_memory
    )


# Testing part

# if __name__ == "__main__":
#     sample_query = "summary of email sent to abhikrishnayanam1999@gmail.com "
#     config = {"configurable": {"thread_id": "1", "user_id": "me"}}
#     state2 = AgentState(query=sample_query)

    # --- Load memory from file into the in-memory store ---
    # load_memory(across_thread_memory, user_id="me")
    
    # Execute the graph
    # response = agent_graph.invoke(state2, config=config)
    
    # # --- Save updated memory to file after graph execution ---
    # save_memory(across_thread_memory, user_id="me")
    
    # # Extract email details safely
    # email_structure = {
    #     "to": response.get("to"),
    #     "subject": response.get("subject"),
    #     "body": response.get("body")
    # }

    # print("\n📧 Final Email Structure:")
    # print(json.dumps(email_structure, indent=2))
    # print(response.get("summary"))

