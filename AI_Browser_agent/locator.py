
# from bs4 import BeautifulSoup
import json
from langgraph.types import Command
from get_llm_response import get_llm_response
from agent_state import BrowserAgentState

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from driver import driver


def llm_dom_locator_node(state: BrowserAgentState) -> Command:
    print("locator_node")
    step = state.next_step or {}

    # Wait for page body to load
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except TimeoutException:
        state.execution_trace.append({"error": "Page body not loaded in time"})

    full_html = driver.page_source

    # --- Call LLM locator ---
    llm_result = get_llm_response(step.get("query", ""), full_html)

    # --- Handle unexpected types ---
    if isinstance(llm_result, str):
        try:
            llm_result = json.loads(llm_result)
        except Exception as e:
            state.execution_trace.append({"llm_raw": llm_result})
            return Command(
                update={"error": f"LLM response parsing failed: {e}"},
                goto="error_node"
            )

    if not isinstance(llm_result, dict):
        state.execution_trace.append({"llm_raw": repr(llm_result)})
        return Command(
            update={"error": f"LLM returned unexpected type: {type(llm_result)}"},
            goto="error_node"
        )

    # --- Debug trace ---
    state.execution_trace.append({"llm_parsed": llm_result})

    # --- Extract fields ---
    target_text = llm_result.get("element_text")
    tag = llm_result.get("tag")
    css_selector = llm_result.get("css_selector")
    xpath = llm_result.get("xpath")

    # --- Validate selectors ---
    if not any([css_selector, xpath, target_text]):
        return Command(
            update={"error": f"LLM could not find usable selector for query: {step.get('query')}"},
            goto="error_node"
        )

    # --- Update state ---
    update_fields = {}
    if target_text: update_fields["target_text"] = str(target_text)
    if tag: update_fields["tag"] = str(tag)
    if css_selector: update_fields["css_selector"] = str(css_selector)
    if xpath: update_fields["xpath"] = str(xpath)

    # --- Decide next node ---
    intent_type = (step.get("intent") or "").lower()
    if intent_type == "extract":
        next_node = "extract_node"
    elif intent_type == "click":
        next_node = "click_node"
    else:
        next_node = "router_node"

    return Command(update=update_fields, goto=next_node)


# # --- Minimal test ---
# if __name__ == "__main__":
#     driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
#     try:
#         driver.get("https://www.demoblaze.com/")

#         # Test click intent
#         state = BrowserAgentState()
#         state.next_step = {"query": "Click the Cart", "intent": "click"}
#         result = llm_dom_locator_node(state, driver)
#         print("Click Test - Next Node:", result.goto)
#         print("Click Test - Step info:", state.next_step)
#         print("Execution trace:", state.execution_trace)
#         print("Error:", state.error)

#         # Test extract intent
#         state = BrowserAgentState()
#         state.next_step = {"query": "Extract the welcome header", "intent": "extract"}
#         result = llm_dom_locator_node(state, driver)
#         print("\nExtract Test - Next Node:", result.goto)
#         print("Extract Test - Step info:", state.next_step)
#         print("Execution trace:", state.execution_trace)
#         print("Error:", state.error)

#     finally:
#         driver.quit()