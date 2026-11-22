# Hybrid AI + Heuristic Self-Healing Playwright Framework

An enterprise-grade UI test automation framework built with Python and Playwright that automatically recovers from broken DOM locators at runtime without human intervention.

## 🚀 Key Architectural Features
- **Zero-Overhead Happy Path**: Standard Playwright actions execute natively with zero AI latency when locators are healthy.
- **DOM Pruning Engine**: Strips non-interactive elements to send lightweight HTML payloads, reducing latency and token consumption by >95%.
- **Two-Tier Hybrid Self-Healing**: Queries Google Gemini AI for semantic CSS selector recovery, with an automatic fallback to a local BeautifulSoup weighted attribute-scoring engine for air-gapped or rate-limited environments.
- **Environment-Aware Execution**: Automatically toggles between headed mode locally and headless Chromium inside GitHub Actions CI/CD pipelines.

## 🏃 Run Locally
1. `pip install -r requirements.txt`
2. `playwright install chromium`
3. Add `GEMINI_API_KEY=your_key` to a `.env` file.
4. Run `pytest -s -v tests/test_login.py`