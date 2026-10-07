
#  AI-Powered Job Scraper & Notifier

An autonomous, serverless Python pipeline that scrapes job boards, applies strict Large Language Model (LLM) filtering to find highly compatible opportunities, and delivers rich notifications via Discord Webhooks.

##  Overview
Hunting for jobs manually is time-consuming and often leads to applying for positions that don't match specific career goals. This project solves that by acting as an autonomous HR assistant. It hunts for job postings, reads the descriptions, and uses the Google Gemini AI to strictly evaluate them against customized professional profiles. Only jobs that pass the exact criteria are sent to specific Discord channels.

##  Features
- **Multi-Profile Targeting:** Capable of running entirely different sets of rules and targets in the same execution (e.g., searching for Software Development roles for Profile A, and Civil Construction roles for Profile B).
- **LLM-Powered Filtering:** Uses Google's Gemini API to act as a strict recruiter, understanding context, required skills, and work models (Remote/Hybrid) instead of just doing simple keyword matching.
- **Serverless Automation:** Designed to be deployed on GitHub Actions using Cron Jobs, running autonomously without hosting costs.
- **Rich Notifications:** Delivers formatted Embed messages directly to Discord via Webhooks, including job summaries and the AI's justification for the match.

##  Tech Stack
- **Language:** Python 3.14+
- **AI Integration:** Google GenAI SDK (`gemini-3.8-flash`)
- **Web Scraping:** `requests`, `BeautifulSoup`
- **Messaging:** Discord Webhooks (JSON Payloads)
- **Environment Management:** `python-dotenv`
- **CI/CD & Automation:** GitHub Actions

##  Architecture (How it Works)
1. **Trigger:** A scheduled GitHub Action wakes up the script.
2. **Scraping (Extract):** The script searches configured job boards and extracts Raw Job Data (Title, Company, Description, Link).
3. **AI Evaluation (Transform):** The raw description is injected into a strictly engineered prompt and sent to the Gemini API. The AI evaluates the job against "Dealbreakers" and "Bonus Preferences".
4. **Delivery (Load):** If the AI responds with an approval, the script formats a JSON Embed and triggers an HTTP POST request to the assigned Discord Webhook.

##  Setup & Installation

**1. Clone the repository**
```bash
git clone https://github.com/Paamzzz/job-notifier$0
```

**2. Create and activate a Virtual Environment**
```
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate   # On Windows
```

**3. Install dependencies**
```
pip install -r requirements.txt
```

**4. Environment Variables**
```
GOOGLE_KEY=your_google_gemini_api_key_here
```
(Note: Webhook URLs are configured directly in the profile dictionaries within the code).

**5. Environment Variables**
```
python3 main.py
```
