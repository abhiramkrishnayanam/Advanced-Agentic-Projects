from langgraph.types import Command
from agent_state import BrowserAgentState
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from driver import driver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, InvalidSelectorException
import time
from locator import llm_dom_locator_node  # your LLM locator

def extract_node(state: BrowserAgentState) -> Command:
    print(f"Executing extract_node for URL: {state.current_url}")
    step = state.next_step
    css_selector = step.get("css_selector")
    xpath = step.get("xpath")
    target_text = step.get("target_text") or step.get("target")

    element = None
    wait = WebDriverWait(driver, 10)

    # 1️⃣ Try CSS selector
    if css_selector:
        try:
            element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, css_selector)))
        except InvalidSelectorException:
            print(f"[WARN] Invalid CSS selector from LLM: {css_selector}")
        except TimeoutException:
            print(f"[WARN] CSS selector not found: {css_selector}")

    # 2️⃣ Try XPath
    if element is None and xpath:
        try:
            element = wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
        except InvalidSelectorException:
            print(f"[WARN] Invalid XPath from LLM: {xpath}")
        except TimeoutException:
            print(f"[WARN] XPath not found: {xpath}")

    # 3️⃣ Fallback: search by visible text ONLY if CSS/XPath were not provided
    if element is None and not css_selector and not xpath and target_text:
        try:
            element = wait.until(EC.visibility_of_element_located(
                (By.XPATH, f"//*[text()='{target_text}']")))
        except TimeoutException:
            print(f"[WARN] Element with text '{target_text}' not found")

    # 4️⃣ If still not found, send to LLM locator node
    if element is None:
        print("[ERROR] Could not locate element, sending to LLM for locator")
        return Command(goto="llm_dom_locator_node")

    # 5️⃣ Extract text
    value = element.text
    print(f"[SUCCESS] Extracted value for '{target_text}': {value}")

    state.execution_trace.append({
        "action": "extract",
        "target": target_text,
        "value": value,
        "result": "success"
    })

    return Command(
        update={
            "current_step": state.current_step + 1,
            "last_extracted": value,
            "current_url": driver.current_url
        },
        goto="router_node"
    )

# if __name__ == "__main__":
#     driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
#     try:
#         driver.get("https://www.demoblaze.com/")
#         time.sleep(1)  # allow page to render

#         state = BrowserAgentState(current_url=driver.current_url)

#         # Step: extract something that Selenium may not immediately find
#         state.next_step = {
#             "query": "Extract the main header 'PRODUCT STORE'",
#             "intent": "extract"
#         }

#         # Call extract_node (it may fallback to LLM)
#         result = extract_node(driver, state)

#         # Handle fallback to LLM locator
#         while result.goto in ["llm_dom_locator_node", "extract_node"]:
#             if result.goto == "llm_dom_locator_node":
#                 print("Routing to LLM locator...")
#                 result = llm_dom_locator_node(state, driver)
#             elif result.goto == "extract_node":
#                 result = extract_node(driver, state)

#         print("Next Node:", result.goto)
#         print("Execution trace:", state.execution_trace)
#         print("Error:", state.error)

#     finally:
#         driver.quit()