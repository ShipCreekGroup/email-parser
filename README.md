# 📧 Email Parser

A Streamlit application that parses unstructured email text (e.g., from Google Docs) into structured email objects using LLM. Perfect for organizing and analyzing email communications for research or data analysis purposes.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://email-parser.streamlit.app/)

## Features

- Parse multiple emails from unstructured text
- Extract structured data: date, sender, subject, preview, body
- Real-time streaming output from LLM
- Export results as JSON or CSV
- Interactive web interface with Streamlit

### How to run it on your own machine

1. Install dependencies

   ```bash
   uv sync
   ```

2. Add LLM_GEMINI_KEY key to `.env` file:

   ```plaintext
   LLM_GEMINI_KEY=your_api_key_here
   ```

3. Run the application

   ```bash
   streamlit run streamlit_app.py
   ```

4. (Occasionally) Export uv lockfile to requirements.txt:

This ensures that streamlit picks up the correct versions of dependencies when
you deploy or share your app.

   ```bash
   uv export --format requirements-txt --output-file requirements.txt
   ```
