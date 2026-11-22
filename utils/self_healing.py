import os
import json
import socket
from datetime import datetime
import requests
import urllib3.util.connection as urllib3_cn
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

CACHE_FILE = "healed_locators.json"

# Force IPv4 to prevent Windows SSL/IPv6 read timeout hangs
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family


def load_healing_cache():
    """Loads previously healed selectors from disk to avoid repeat AI calls."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_to_healing_cache(broken_selector, description, healed_data):
    """Persists newly healed selectors and audit metadata to disk."""
    cache = load_healing_cache()
    cache[broken_selector] = {
        "description": description,
        "healed_selector": healed_data["healed_selector"],
        "confidence": healed_data.get("confidence", "UNKNOWN"),
        "reason": healed_data.get("reason", ""),
        "healed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def local_heuristic_heal(interactive_html, element_description):
    """Weighted semantic attribute scoring fallback for offline/rate-limited environments."""
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
    """Two-Tier Hybrid Self-Healing Engine (Cloud Gemini + Local Heuristic)."""
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
            response = requests.post(base_url, params={"key": api_key}, json=payload, timeout=3)
            response.raise_for_status()
            data = response.json()
            ai_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(ai_text)
        except Exception as e:
            print(f"   [Cloud AI Notice] Cloud endpoint unreachable ({type(e).__name__}). Engaging Local Heuristic Engine...")

    return local_heuristic_heal(interactive_html, element_description)


def extract_interactive_elements(page):
    """Extracts only interactive DOM nodes to minimize payload size."""
    elements = page.locator("input, button, a, select, textarea").evaluate_all(
        "els => els.map(e => e.outerHTML)"
    )
    return "\n".join(elements)


def resolve_and_execute(page, selector, description, action_fn):
    """
    Core Production Wrapper:
    1. Checks Healing Cache first (0ms latency)
    2. Tries Primary Selector
    3. Triggers Hybrid AI/Heuristic Healing & updates Cache
    """
    cache = load_healing_cache()
    if selector in cache:
        cached_selector = cache[selector]["healed_selector"]
        print(f"⚡ [Cache Hit] Using previously healed selector '{cached_selector}' for '{description}'")
        action_fn(cached_selector, timeout=3000)
        return

    try:
        action_fn(selector, timeout=3000)
        print(f"✅ [Standard] Executed '{description}' using '{selector}'")
    except Exception:
        print(f"⚠️ [Broken Locator] Failed to find '{description}' using '{selector}'. Triggering Self-Healing...")
        clean_elements = extract_interactive_elements(page)
        result = get_healed_selector(clean_elements, selector, description)
        
        if result and result.get("healed_selector"):
            new_selector = result["healed_selector"]
            print(f"🩹 [Healed!] New Selector: '{new_selector}' (Confidence: {result.get('confidence')})")
            print(f"   Reason: {result.get('reason')}")
            
            # Save to persistent cache & audit log
            save_to_healing_cache(selector, description, result)
            action_fn(new_selector, timeout=5000)
        else:
            raise Exception(f"❌ Self-healing failed for '{description}'. Could not locate element.")


def smart_fill(page, selector, text_value, description):
    resolve_and_execute(
        page, selector, description,
        lambda sel, timeout: page.locator(sel).fill(text_value, timeout=timeout)
    )


def smart_click(page, selector, description):
    resolve_and_execute(
        page, selector, description,
        lambda sel, timeout: page.locator(sel).click(timeout=timeout)
    )
