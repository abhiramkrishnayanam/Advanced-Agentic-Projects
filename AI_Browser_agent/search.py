from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from langgraph.types import Command
from selenium.webdriver.common.keys import Keys
from agent_state import BrowserAgentState
from driver import driver
from urllib.parse import quote_plus

# Search configuration for supported platforms
SEARCH_CONFIG = {
    "google": {
        "url": "https://www.google.com",
        "selector": "input[name='q']",
        "submit": "enter"
    },
    "wikipedia": {
        "url": "https://www.wikipedia.org",
        "selector": "input[name='search']",
        "submit": "return"
    },
    "bing": {
        "url": "https://www.bing.com",
        "selector": "#sb_form_q",
        "submit": "enter"
    }
}

def search_node(state: BrowserAgentState) -> Command:
    """
    Executes a search on Google, Wikipedia, or Bing based on the normalized target.
    Enhanced: waits for results to be interactable and optionally fetches first link.
    """
    print("search_node")
    step = state.next_step
    query = step.get("query")
    target_raw = step.get("target", "").lower()

    # Normalize target names
    if "google" in target_raw:
        target = "google"
    elif "wikipedia" in target_raw:
        target = "wikipedia"
    elif "bing" in target_raw:
        target = "bing"
    else:
        target = target_raw  # fallback

    try:
        if target not in SEARCH_CONFIG:
            raise ValueError(f"Unsupported search target: {target}")

        cfg = SEARCH_CONFIG[target]
        print(f"[SEARCH] Target: {target}, Query: {query}")

        if target == "google":
            # Directly navigate to search results to avoid popups
            search_url = f"https://www.google.com/search?q={quote_plus(query)}"
            driver.get(search_url)

            # Wait for search results to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.g"))
            )
            
            # Wait until at least the first result link is clickable
            first_link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "(//div[@id='search']//div[contains(@class,'g')]//a)[1]"))
            )
            # Store first link info in state for click_node if needed
            state.dom_snapshot['first_google_link'] = first_link

        elif target == "wikipedia":
            # Navigate to Wikipedia main page
            driver.get(cfg["url"])
            search_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, cfg["selector"]))
            )
            search_box.clear()
            search_box.send_keys(query)
            search_box.send_keys(Keys.RETURN)

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.mw-search-results, div#content"))
            )

        elif target == "bing":
            # Navigate to Bing main page
            driver.get(cfg["url"])
            
            # Wait until search box is clickable
            search_box = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, cfg["selector"]))
            )
            
            search_box.clear()
            search_box.send_keys(query)
            search_box.send_keys(Keys.RETURN)

            # Wait for search results to appear
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.b_algo"))
            )

        print(f"[SUCCESS] Search executed for '{query}' on {target}")

        state.execution_trace.append({
            "action": "search",
            "target": target,
            "query": query,
            "url": driver.current_url,
            "result": "success"
        })

    except Exception as e:
        state.error = f"Search failed: {e}"
        print(state.error)
        state.execution_trace.append({
            "action": "search",
            "target": target,
            "query": query,
            "result": "failed",
            "error": str(e)
        })
        return Command(
            update={"error": str(e)},
            goto="error_node"
        )

    # Return control to router_node
    return Command(
        update={
            "current_step": state.current_step + 1,
            "current_url": driver.current_url
        },
        goto="router_node"
    )
# state = BrowserAgentState(
#     next_step={"query": "Selenium automation", "target": "google"}
# )
# command = search_node(state)
# if state.error:
#     print("Error:", state.error)
# else:
#     print("Execution Trace:", state.execution_trace)
#     print("Next Node:", command.goto)
# driver.close()