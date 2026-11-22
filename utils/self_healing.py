import os
import json
import socket
import requests
import urllib3.util.connection as urllib3_cn
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# Force IPv4 to prevent Windows SSL/IPv6 read timeout hangs
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family


def local_heuristic_heal(interactive_html, element_description):
    """
    Enterprise Fallback: Uses weighted semantic attribute scoring (ignoring generic
    words like 'input' or 'field') to pinpoint the exact matching DOM element.
    """
    soup = BeautifulSoup(interactive_html, "html.parser")
    stop_words = {"input", "field", "button", "submit", "click", "the", "for", "box"}
    keywords = [w.lower() for w in element_description.split() if w.lower() not in stop_words and len(w) > 2]
    
    best_tag = None
    highest_score = 0

    for tag in soup.find_all(["input", "button", "a"]):
        attrs_str = " ".join([str(v).lower() for v in tag.attrs.values()]) + " " + tag.text.lower()
        score = sum(1 for kw in keywords if kw in attrs_str)
        if score > highest_score:
            highest_score = score
            best_tag = tag

    if best_tag:
        if best_tag.get("id"):
            return {
                "healed_selector": f"#{best_tag['id']}",
                "confidence": "HIGH (Local Heuristic)",
                "reason": f"Matched element ID '{best_tag['id']}' via weighted semantic scoring."
            }
        elif best_tag.get("name"):
            return {
                "healed_selector": f"[name='{best_tag['name']}']",
                "confidence": "MEDIUM (Local Heuristic)",
                "reason": f"Matched element name '{best_tag['name']}' via weighted semantic scoring."
            }
    return None


def get_healed_selector(interactive_html, broken_selector, element_description):
    """
    Hybrid Self-Healing Engine: Tries Cloud Gemini AI first over IPv4, 
    and seamlessly falls back to local DOM heuristics if offline/blocked.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    sub = "generativelanguage"
    domain = "googleapis.com"
    path = "/v1beta/models/gemini-3.8-flash:generateContent"
    base_url = f"https://{sub}.{domain}{path}"

    prompt = (
        "You are an expert QA Automation Architect. A Playwright locator failed. "
        "Analyze the HTML elements and return ONLY a JSON object with keys: "
        "'healed_selector', 'confidence', and 'reason'.\n\n"
        f"Element Description: {element_description}\n"
        f"Broken Selector: {broken_selector}\n"
        f"HTML:\n{interactive_html}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json"
        }
    }

    if api_key:
        try:
            response = requests.post(base_url, params={"key": api_key}, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            ai_text = data["candidates"]["content"]["parts"]["text"]
            return json.loads(ai_text)
        except Exception as e:
            print(f"   [Cloud AI Notice] Cloud endpoint unreachable ({type(e).__name__}). Engaging Local Heuristic Engine...")

    return local_heuristic_heal(interactive_html, element_description)


def extract_interactive_elements(page):
    """Extracts only inputs, buttons, and links to keep the payload tiny and fast."""
    elements = page.locator("input, button, a, select, textarea").evaluate_all(
        "els => els.map(e => e.outerHTML)"
    )
    return "\n".join(elements)


def smart_fill(page, selector, text_value, description):
    """Attempts to type text using the primary locator; self-heals if broken."""
    try:
        page.locator(selector).fill(text_value, timeout=3000)
        print(f"✅ [Standard] Filled '{description}' using '{selector}'")
    except Exception:
        print(f"⚠️ [Broken Locator] Failed to find '{description}' using '{selector}'. Triggering Self-Healing...")
        clean_elements = extract_interactive_elements(page)
        result = get_healed_selector(clean_elements, selector, description)
        
        if result and result.get("healed_selector"):
            new_selector = result["healed_selector"]
            print(f"🩹 [Healed!] New Selector: '{new_selector}' (Confidence: {result.get('confidence')})")
            print(f"   Reason: {result.get('reason')}")
            page.locator(new_selector).fill(text_value, timeout=5000)
        else:
            raise Exception(f"❌ Self-healing failed for '{description}'. Could not locate element.")


def smart_click(page, selector, description):
    """Attempts to click an element using the primary locator; self-heals if broken."""
    try:
        page.locator(selector).click(timeout=3000)
        print(f"✅ [Standard] Clicked '{description}' using '{selector}'")
    except Exception:
        print(f"⚠️ [Broken Locator] Failed to find '{description}' using '{selector}'. Triggering Self-Healing...")
        clean_elements = extract_interactive_elements(page)
        result = get_healed_selector(clean_elements, selector, description)
        
        if result and result.get("healed_selector"):
            new_selector = result["healed_selector"]
            print(f"🩹 [Healed!] New Selector: '{new_selector}' (Confidence: {result.get('confidence')})")
            print(f"   Reason: {result.get('reason')}")
            page.locator(new_selector).click(timeout=5000)
        else:
            raise Exception(f"❌ Self-healing failed for '{description}'. Could not locate element.")
