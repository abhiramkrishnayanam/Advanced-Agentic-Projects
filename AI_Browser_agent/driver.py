from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

options = Options()
options.add_experimental_option("detach", True)  # keep browser open
options.add_argument("--incognito")              # incognito mode
options.add_argument("--disable-blink-features=AutomationControlled")  # avoid bot detection
options.add_argument("--ignore-certificate-errors")
options.add_argument("--disable-extensions")     # disable extensions
options.add_argument("--start-maximized")        # optional

# Disable proxy completely
options.add_argument("--no-proxy-server")
options.add_argument("--proxy-bypass-list=*")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)
