from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from langgraph.types import Command
from agent_state import BrowserAgentState
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
    StaleElementReferenceException
)
from driver import driver

def click_node(state: BrowserAgentState) -> Command:
    print("[CLICK NODE] Executing click_node")
    step = state.next_step

    # Special case: Google first search result stored from search_node
    if step.get("intent") == "click" and step.get("target") == "first link":
        element = state.dom_snapshot.get("first_google_link")
        if element:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                element.click()
                print("[CLICK NODE] Clicked first Google link from snapshot successfully")
                state.execution_trace.append({
                    "action": "click",
                    "intent": step.get("intent"),
                    "target": "first_google_link",
                    "locator_type": "snapshot",
                    "result": "success"
                })
                return Command(
                    update={
                        "current_step": state.current_step + 1,
                        "current_url": driver.current_url
                    },
                    goto="router_node"
                )
            except Exception as e:
                print(f"[CLICK NODE] Failed to click first link from snapshot: {e}")

        # Fallback to XPath if snapshot not available
        selector = "(//div[@id='search']//div[contains(@class,'g')]//a)[1]"
        locator_type = By.XPATH
    else:
        # Determine locator for general clicks
        selector = step.get("css_selector") or step.get("xpath") or step.get("target_text") or step.get("target")
        if not selector:
            print("[CLICK NODE] No selector found, routing to LLM locator...")
            return Command(goto="llm_dom_locator_node")

        selector = str(selector)
        if step.get("css_selector"):
            locator_type = By.CSS_SELECTOR
        elif step.get("xpath"):
            locator_type = By.XPATH
        elif step.get("target_text") or step.get("target"):
            locator_type = By.PARTIAL_LINK_TEXT
        else:
            return Command(goto="llm_dom_locator_node")

    try:
        wait = WebDriverWait(driver, 30)
        element = wait.until(EC.element_to_be_clickable((locator_type, selector)))

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)

        try:
            element.click()
            print(f"[CLICK NODE] Clicked element successfully using {locator_type}: {selector}")
        except (ElementClickInterceptedException, StaleElementReferenceException):
            # Handle modals or overlays
            for modal in driver.find_elements(By.CSS_SELECTOR, ".modal, .popup, [class*='overlay']"):
                if modal.is_displayed():
                    try:
                        close_btn = modal.find_element(By.CSS_SELECTOR, ".close, button")
                        close_btn.click()
                        print("[CLICK NODE] Closed modal/overlay")
                    except Exception:
                        pass
            driver.execute_script("arguments[0].click();", element)
            print(f"[CLICK NODE] Clicked element via JS after handling overlays: {selector}")

        state.execution_trace.append({
            "action": "click",
            "intent": step.get("intent"),
            "target": selector,
            "locator_type": str(locator_type),
            "result": "success"
        })

    except (TimeoutException, NoSuchElementException, ElementClickInterceptedException) as e:
        print(f"[CLICK NODE] Click failed for '{selector}': {str(e)}. Routing to LLM locator.")
        state.execution_trace.append({
            "action": "click",
            "intent": step.get("intent"),
            "target": selector,
            "locator_type": str(locator_type),
            "result": f"failed: {str(e)}"
        })
        return Command(goto="llm_dom_locator_node")

    except Exception as e:
        state.error = f"Click failed: {str(e)}"
        return Command(update={"error": str(e)}, goto="error_node")

    # Update state and go to next step
    return Command(
        update={
            "current_step": state.current_step + 1,
            "current_url": driver.current_url
        },
        goto="router_node"
    )

# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager
# from locator import llm_dom_locator_node


# # --- Minimal test ---
# if __name__ == "__main__":
#     driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
#     try:
#         driver.get("https://www.demoblaze.com/")
#         WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "cartur")))

#         state = BrowserAgentState()
#         state.next_step = {
#             "css_selector": "#cartur",  # directly use CSS selector for simplicity
#             "intent": "click"
#         }

#         result = click_node(driver, state)

#         print("Node returned:", getattr(result, "goto", result))
#         print("Execution trace:", state.execution_trace)
#         print("Error:", state.error)

#     finally:
#         driver.quit()