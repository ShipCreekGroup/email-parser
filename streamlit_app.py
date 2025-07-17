import csv
import io
import json
import logging

import jsonschema
import llm
import streamlit as st

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EMAIL_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "email_name": {
                "type": "string",
                "description": "A descriptive name for the email (derived from the subject or content)",
            },
            "sender": {
                "type": "string",
                "description": "The sender's name (Ted Eischeid, Team Eischeid, Les Gara, etc.)",
            },
            "subject": {"type": "string", "description": "The email subject line"},
            "preview": {
                "type": "string",
                "description": "The preview text that would appear in an email client",
            },
            "body": {
                "type": "string",
                "description": "The full email content with line breaks preserved",
            },
        },
        "required": ["email_name", "sender", "subject", "preview", "body"],
        "additionalProperties": False,
    },
}


def get_response(text: str, *, response_container) -> str:
    """Get raw response from LLM."""
    # model = llm.get_model("gemini-2.0-flash")
    model = llm.get_model("gemini-2.5-flash-lite-preview-06-17")

    prompt = f"""
Parse the following text into an array of email objects. Each email should have:
- email_name: A descriptive name (derived from subject/content)
- sender: The sender's name
- subject: The email subject line  
- preview: Preview text for email client
- body: Full email content with line breaks preserved

Return only valid JSON matching this schema:
{json.dumps(EMAIL_SCHEMA, indent=2)}

Text to parse:
{text}
"""

    response = model.prompt(prompt, schema=EMAIL_SCHEMA, stream=True)

    stream_placeholder = response_container.empty()

    raw_response = ""
    for chunk in response:
        raw_response += chunk
        stream_placeholder.code(raw_response, language="json")

    return raw_response


def parse_response(raw_response: str, *, error_container) -> list[dict[str, str]]:
    """Parse and validate raw LLM response."""
    try:
        emails = json.loads(raw_response)
        jsonschema.validate(emails, EMAIL_SCHEMA)
        return emails
    except json.JSONDecodeError as e:
        error_msg = f"JSON decode error: {e}"
        logger.error(error_msg)
        error_container.error(f"**❌ JSON Parse Failed:** {error_msg}")
        error_container.write(f"**Raw response that failed:** {raw_response}")
        raise ValueError(error_msg)
    except jsonschema.ValidationError as e:
        error_msg = f"Schema validation error: {e.message}"
        logger.error(error_msg)
        error_container.error(f"**❌ Schema Validation Failed:** {error_msg}")
        error_container.write(f"**Failed at path:** {list(e.absolute_path)}")
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        logger.error(error_msg)
        error_container.error(f"**❌ Unexpected Error:** {error_msg}")
        error_container.write(f"**Raw response:** {raw_response}")
        raise ValueError(error_msg)


def emails_to_csv(emails: list[dict[str, str]]) -> str:
    """Convert list of email objects to CSV format."""
    output = io.StringIO()
    field_names = ["email_number", "email_name", "sender", "subject", "preview", "body"]
    writer = csv.DictWriter(output, fieldnames=field_names, delimiter="\t")
    writer.writeheader()
    for i, email in enumerate(emails, 1):
        writer.writerow({
            "email_number": i,
            **email
        })
    return output.getvalue()

def main():
    st.set_page_config(
        page_title="Email Parser",
        page_icon="📧",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    
    # Custom CSS for better layout
    st.markdown("""
    <style>
    .stExpander > div:first-child > div > div > div > div > div > div > div {
        max-height: 400px;
        overflow-y: auto;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("📧 Email Parser")
    st.write("Parse copy-pasted text from Google Docs into structured email objects")

    input_text = st.text_area(
        "Paste your text here:",
        height=300,
        placeholder="Paste your email text from Google Docs here...",
    )

    parse_button = st.button("Parse Emails", type="primary")

    if parse_button and input_text.strip():
        raw_output_expander = st.expander("🔍 Raw LLM Output", expanded=False)
        
        try:
            with st.spinner("Receiving response from LLM..."):
                with raw_output_expander:
                    response_container = st.container()
                    raw_response = get_response(input_text, response_container=response_container)
                error_container = st.container()
                emails = parse_response(raw_response, error_container=error_container)

            st.success(f"Successfully parsed {len(emails)} email(s)!")

            tab1, tab2, tab3 = st.tabs(["📧 Pretty View", "📄 JSON", "📊 CSV"])
            
            with tab1:
                for i, email in enumerate(emails, 1):
                    with st.expander(f"Email {i}: {email['email_name']}", expanded=False):
                        st.write(f"**Sender:** {email['sender']}")
                        st.write(f"**Subject:** {email['subject']}")
                        st.write(f"**Preview:** {email['preview']}")
                        st.write("**Body:**")
                        st.text(email["body"])
            
            with tab2:
                st.json(emails)
            
            with tab3:
                csv_data = emails_to_csv(emails)
                st.code(csv_data, language="csv", line_numbers=True)

        except Exception as e:
            st.error(f"Error parsing emails: {e}")
            with raw_output_expander:
                response_container.error(f"**Final error:** {e}")


if __name__ == "__main__":
    main()
