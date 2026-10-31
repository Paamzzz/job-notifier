# 🤖 AI-Powered Job Scraper & Notifier

An autonomous, serverless Python pipeline that scrapes multiple Brazilian and global job boards simultaneously, applies strict Large Language Model (LLM) filtering to find highly compatible opportunities, and delivers rich notifications via Discord Webhooks.

## 📖 Overview
Hunting for jobs manually across dozens of platforms is time-consuming and often leads to applying for positions that don't match specific career goals. This project solves that by acting as an autonomous HR assistant. It hunts for job postings across **LinkedIn, Gupy, Indeed, InfoJobs, Vagas.com.br, Catho, Trabalha Brasil, Programathor, and GitHub Vagas**, reads the descriptions, and uses the **Google Gemini AI** to strictly evaluate them against customized professional profiles. Only jobs that pass the exact criteria are sent to specific Discord channels.

## ✨ Features
- **Multi-Source Job Scraping:** Concurrent scraping (`ThreadPoolExecutor`) across 9+ major job sources:
  - **LinkedIn** (Guest Jobs API + full job description extraction)
  - **Gupy** (Official public portal API with remote/hybrid/city metadata)
  - **Indeed Brasil** (Direct structured extraction + indexed fallback)
  - **InfoJobs** (JSON-LD & HTML job cards + indexed fallback)
  - **Vagas.com.br** (Direct search & role details)
  - **Catho** (`__NEXT_DATA__` JSON & HTML parser + indexed fallback)
  - **Trabalha Brasil** (Great coverage for technical, civil construction, and entry-level roles)
  - **Programathor** (Tech-specialized Brazilian platform)
  - **GitHub Vagas BR** (`backend-br`, `frontendbr`, `react-brasil`, `pybr`, `datascience-br`)
- **Multi-Profile Targeting:** Runs completely independent search keywords, locations, and evaluation rules in the same execution (e.g., **Pamela - Tech** for Software/AI roles in RJ or Remote, and **Nycollas - Edificações** for Civil Construction/CAD roles in Curitiba or Remote).
- **LLM-Powered Filtering:** Uses Google's Gemini API to act as a strict recruiter, evaluating dealbreakers, salary floors, work models (Remote/Hybrid/On-site), and bonus preferences.
- **Smart Deduplication:** Saves evaluated job IDs in `historico_vagas.json` to avoid duplicate evaluations and repeated Discord notifications.
- **Serverless Automation:** Ready to run autonomously on GitHub Actions via Cron Jobs (`.github/workflows/job_notifier.yml`).
- **Rich Notifications:** Delivers formatted Embed messages directly to Discord via Webhooks, including company, location, platform, match score (`0-100`), and the AI's justification.

## 🛠️ Tech Stack
- **Language:** Python 3.12+
- **AI Integration:** Google GenAI SDK (`google-genai`)
- **Web Scraping:** `requests`, `BeautifulSoup4`, `concurrent.futures`
- **Messaging:** Discord Webhooks (Rich JSON Embeds)
- **Environment Management:** `python-dotenv`
- **CI/CD & Automation:** GitHub Actions

## ⚙️ Architecture (How it Works)
1. **Trigger:** A scheduled GitHub Action (or local execution) starts `main.py`.
2. **Scraping (Extract):** `scraper.py` queries all job boards in parallel for each profile's target keywords and locations, normalizing and deduplicating results.
3. **Pre-Filter & History Check:** Filters out already-evaluated jobs (`historico_vagas.json`) and titles containing blocked seniority levels (e.g., Senior, Director).
4. **AI Evaluation (Transform):** Injects the full job metadata and description into the profile's prompt and sends it to the Gemini API, parsing `APROVADA`, `NOTA`, and `RESUMO`.
5. **Delivery (Load):** Approved jobs trigger a rich Discord Embed notification to the profile's dedicated Webhook URL.

## 🚀 Setup & Installation

**1. Clone the repository**
```bash
git clone https://github.com/Paamzzz/job-notifier.git
cd job-notifier
```

**2. Create and activate a Virtual Environment**
```bash
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate   # On Windows
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure Environment Variables (`.env`)**
Create a `.env` file in the root directory:
```env
GOOGLE_KEY=your_google_gemini_api_key_here
WEBHOOK_DEV=https://discord.com/api/webhooks/your_tech_webhook
WEBHOOK_EDIFICACOES=https://discord.com/api/webhooks/your_edificacoes_webhook
LIMITE_VAGAS_POR_PERFIL=25
```

**5. Run the project**
```bash
python3 main.py
```
