import warnings
from dotenv import load_dotenv
warnings.filterwarnings('ignore')
load_dotenv(override=True)

from langchain_groq import ChatGroq
from selenium.webdriver.chrome.webdriver import WebDriver
from langgraph.types import Command
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
import json

from driver import driver
from locator import llm_dom_locator_node
from click_file import click_node
from search import search_node
from extractor import extract_node
from agent_state import BrowserAgentState


llm= ChatGroq(model="openai/gpt-oss-20b", temperature= 0)



def intent_parser_node(state: BrowserAgentState) -> Command:
    query = state.user_query
    prompt = f"""
You are an intent extraction assistant for a browser automation agent.
The user will give a natural language command about browsing the web.

Convert the command into a sequence of steps in a JSON array format.
Each step must follow this structure:
{{
  "intent": "<one of: navigate, search, click, extract, login, custom>",
  "target": "<website or element if mentioned>",
  "query": "<search query or action text if applicable>",
  "target_text": "<the visible text of the element, if applicable>",
  "css_selector": "<the CSS selector of the element, if applicable>"
}}

Rules:
- Always return a strictly valid JSON array (no extra text or explanations).
- If the user mentions a website, use its canonical URL (e.g., Google → https://www.google.com).
- For search actions, use the search engine's URL directly for Google, Bing, or Wikipedia.
- For click actions:
  - Fill either 'target_text' or 'css_selector' (prefer CSS selector if known)
  - For Google search results, if the user wants "first link", use XPath: "(//div[@id='search']//div[contains(@class,'g')]//a)[1]"
  - Ensure the selector works with Selenium.
- If the element or selector is unknown, leave 'target_text' or 'css_selector' empty.

Example conversions:
- "search on Wikipedia" → {{"intent": "navigate", "target": "Wikipedia", "query": "https://en.wikipedia.org"}}
- "click the Cart button on Demoblaze" → {{"intent": "click", "target": "Cart", "query": "Cart", "target_text": "Cart", "css_selector": "#cartur"}}

User command:
{query}
"""
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw_output = response.content.strip()
        print("LLM raw output:", raw_output)

        # Remove triple backticks if present
        if raw_output.startswith("```"):
            raw_output = raw_output.split("\n", 1)[1]  # remove first line ```
            raw_output = raw_output.rsplit("```", 1)[0]  # remove last line ```

        parsed_intent = json.loads(raw_output)
        print(f"[INTENT PARSER] Successfully parsed intent: {parsed_intent}")

    except Exception as e:
        state.error = str(e)
        return Command(update={"error": str(e)}, goto="error_node")

    return Command(
        update={"intent": parsed_intent},
        goto="router_node"
    )



def router_node(state: BrowserAgentState) -> Command:
    print("=== router_node ===")
    print("state.intent:", state.intent)
    print("Current state:", state.__dict__)

    # Initialize action_plan only once
    if state.action_plan is None or len(state.action_plan) == 0:
        if not state.intent:
            state.error = "No intent found from parser"
            print("[ROUTER ERROR] No intent found")
            return Command(update={"error": state.error}, goto="error_node")
        state.action_plan = state.intent.copy()
        print("[ROUTER] Initialized action_plan:", state.action_plan)

    # Check if all steps are done
    if state.current_step >= len(state.action_plan):
        print("[ROUTER] All steps completed")
        return Command(goto=END)

    # Get current step
    step = state.action_plan[state.current_step]
    print(f"[ROUTER] Executing step {state.current_step}: {step}")

    intent_type = step.get("intent", "").strip().lower()
    allowed_intents = {"navigate", "search", "click", "extract", "login", "custom"}

    if intent_type not in allowed_intents:
        state.error = f"Unknown intent: {intent_type}"
        print("[ROUTER ERROR]", state.error)
        return Command(update={"error": state.error}, goto="error_node")

    # Pass next_step downstream; do NOT increment current_step here
    return Command(
        update={"next_step": step},
        goto=f"{intent_type}_node"
    )

def navigate_node(state: BrowserAgentState) -> Command:
    print("navigate_node")
    step = state.next_step
    if step is None:
        return Command(update={"error": "No next_step found"}, goto="error_node")

    url = step.get("query") or step.get("url")
    if not url:
        return Command(update={"error": "No URL provided"}, goto="error_node")

    try:
        print(f"[NAVIGATE] Opening URL: {url}")
        driver.get(url)

        # Update execution trace
        state.execution_trace.append({
            "action": "navigate",
            "target": step.get("target"),
            "url": url,
            "final_url": driver.current_url,
            "result": "success"
        })

    except Exception as e:
        state.execution_trace.append({
            "action": "navigate",
            "target": step.get("target"),
            "url": url,
            "result": "failed",
            "error": str(e)
        })
        return Command(update={"error": str(e)}, goto="error_node")

    # Increment current_step via Command so LangGraph knows to move forward
    return Command(
        update={"current_step": state.current_step + 1, "current_url": driver.current_url},
        goto="router_node"
    )

def error_node(state: BrowserAgentState) -> Command:
    # Log the error
    error_info = state.error if state.error else "Unknown error occurred"
    print(f"[ERROR NODE] Execution stopped. Error: {error_info}")
    
    # Optionally, add to execution trace
    state.execution_trace.append({"action": "error", "message": error_info})
    
    # Stop the workflow
    return Command(goto="END")



graph = StateGraph(BrowserAgentState)
graph.add_node("intent_parser_node",intent_parser_node)
graph.add_node("router_node",router_node)
graph.add_node("navigate_node",navigate_node)
graph.add_node("error_node", error_node)
graph.add_node("click_node",click_node)
graph.add_node("extract_node", extract_node)
graph.add_node("search_node", search_node)
graph.add_node("llm_dom_locator_node", llm_dom_locator_node)


graph.add_edge(START, "intent_parser_node")
graph.add_edge("error_node", END)

browser_graph = graph.compile()


if __name__ == "__main__":
    # Initialize state
    state = BrowserAgentState()
    state.user_query = "I need to buy a bag below 1000 rs search for it and click the first link shown in google"
    state.execution_trace = []

    # Invoke the graph
    final_state = browser_graph.invoke(state)

    # Print execution trace
    print("\n=== Execution Trace ===")
    for step in getattr(final_state, "execution_trace", []):
        print(step)

    # Print final URL
    print("\nFinal URL:", getattr(final_state, "current_url", None))

    # Check for errors
    if getattr(final_state, "error", None):
        print("\nError:", final_state.error)
    else:
        print("\nNavigation executed successfully!")
    
    # driver.quit()

