from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    NoAlertPresentException,
    UnexpectedAlertPresentException,
)
from datetime import datetime
import time

BUTTON_CLASS = "availableBtn"
MAX_CLICKS = 50  # safety limit

# Walks up from a button to the smallest container holding exactly one
# "REQUEST #12345" and returns that number, so each card gets a stable ID
# that survives re-renders / page reloads.
_REQUEST_ID_JS = """
let el = arguments[0];
for (let i = 0; i < 10 && el; i++) {
    el = el.parentElement;
    if (!el) break;
    const m = (el.innerText || '').match(/REQUEST\\s*#\\s*(\\d+)/gi);
    if (m && m.length === 1) return m[0].replace(/\\D/g, '');
    if (m && m.length > 1) return null;   // walked past the card
}
return null;
"""


def _dismiss_alert(driver):
    """Accept a JS alert/confirm if the site pops one up after a click."""
    try:
        alert = driver.switch_to.alert
        print(f"  Alert: {alert.text!r} -> accepting")
        alert.accept()
        return True
    except NoAlertPresentException:
        return False


def _request_id(driver, button, fallback):
    try:
        rid = driver.execute_script(_REQUEST_ID_JS, button)
    except StaleElementReferenceException:
        return None
    return rid or fallback


def accept_appointments(url, headless=False, timeout=15):
    """Click the 'Available' button on every request card on the page.

    Returns the number of requests clicked (0 if none).
    """
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=chrome_options)

    done = set()       # request IDs already clicked
    accepted = 0

    try:
        driver.get(url)
        print("Page loaded...")

        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CLASS_NAME, BUTTON_CLASS))
            )
        except TimeoutException:
            print("No 'available' buttons found on the page")
            _screenshot(driver, "no_buttons")
            return 0

        initial = len(driver.find_elements(By.CLASS_NAME, BUTTON_CLASS))
        print(f"Found {initial} button(s)")

        for _ in range(MAX_CLICKS):
            _dismiss_alert(driver)

            # Re-find every pass: the DOM may have changed after the last click
            buttons = driver.find_elements(By.CLASS_NAME, BUTTON_CLASS)

            # Pick the first button whose request we haven't handled yet.
            # (The old code indexed into the list with i, but the list shrinks
            #  after each click, so it skipped every other button and then hit
            #  `i >= len(buttons)` and stopped after the first one.)
            target, target_id = None, None
            for idx, b in enumerate(buttons):
                rid = _request_id(driver, b, fallback=f"btn-{idx}-{len(buttons)}")
                if rid and rid not in done:
                    target, target_id = b, rid
                    break

            if target is None:
                break  # everything on the page has been handled

            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", target
                )
                driver.execute_script("arguments[0].click();", target)
            except StaleElementReferenceException:
                continue  # page re-rendered under us; re-find and retry
            except UnexpectedAlertPresentException:
                _dismiss_alert(driver)

            done.add(target_id)
            accepted += 1
            print(f"✓ Clicked request {target_id}")

            _dismiss_alert(driver)
            # Give the site time to save; if the click reloads the page,
            # wait for the old element to go stale before continuing.
            try:
                WebDriverWait(driver, 3).until(EC.staleness_of(target))
                WebDriverWait(driver, timeout).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except TimeoutException:
                pass  # no reload, just an in-page update
            time.sleep(1)

        # Best-effort confirmation from the page text
        try:
            text = driver.find_element(By.TAG_NAME, "body").text.upper()
            confirmed = text.count("CURRENT STATUS: AVAILABLE")
            print(f"Page now shows {confirmed} request(s) with status AVAILABLE")
        except Exception:
            pass

        print(f"Total clicked: {accepted}")
        if accepted < initial:
            _screenshot(driver, "partial")
        return accepted

    except Exception as e:
        print(f"Error accepting appointments: {e}")
        _screenshot(driver, "error")
        return accepted

    finally:
        driver.quit()


def _screenshot(driver, label):
    name = f"{label}_{datetime.now():%Y%m%d_%H%M%S}.png"
    try:
        driver.save_screenshot(name)
        print(f"  Saved screenshot {name}")
    except Exception:
        pass
