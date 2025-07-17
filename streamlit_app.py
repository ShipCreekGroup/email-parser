import csv
import io
import json
import logging

import jsonschema
import llm
import partial_json_parser
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
                "description": "A short unique name that identifies the email. Either supplied directly, or derived from the subject or content.",
            },
            "sender": {
                "type": "string",
                "description": "The sender's name.",
            },
            "subject": {"type": "string", "description": "The email subject line"},
            "preview": {
                "type": "string",
                "description": "The preview text that would appear in an email client.",
            },
            "body": {
                "type": "string",
                "description": "The full email content with line breaks preserved.",
            },
            "date": {
                "type": "string",
                "description": "The email date in yyyy-mm-dd format (optional).",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
            },
        },
        "required": ["email_name", "sender", "subject", "preview", "body"],
        "additionalProperties": False,
    },
}


def stream_response(text: str):
    """Stream raw response chunks from LLM."""
    # model = llm.get_model("gemini-2.0-flash")
    model = llm.get_model("gemini-2.5-flash-lite-preview-06-17")

    prompt = f"""
Parse the following text into an array of email objects.

Return only valid JSON matching this schema:
{json.dumps(EMAIL_SCHEMA, indent=2)}

Text to parse:
{text}
""".strip()

    response = model.prompt(prompt, schema=EMAIL_SCHEMA, stream=True)
    
    for chunk in response:
        yield chunk


def parse_response_partial(raw_response: str) -> list[dict[str, str]] | None:
    """Parse partial JSON response without validation."""
    try:
        emails = partial_json_parser.loads(raw_response)
        schema_with_fields_optional = EMAIL_SCHEMA.copy()
        schema_with_fields_optional["items"]["required"] = []
        jsonschema.validate(emails, schema_with_fields_optional)
        return emails
    except Exception:
        return None


def parse_response_full(raw_response: str, *, error_container) -> list[dict[str, str]]:
    """Parse and validate complete LLM response."""
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
    field_names = ["email_number", "date", "email_name", "sender", "subject", "preview", "body" ]
    writer = csv.DictWriter(output, fieldnames=field_names, delimiter="\t")
    writer.writeheader()
    for i, email in enumerate(emails, 1):
        writer.writerow({
            "email_number": i,
            "date": email.get("date", ""),
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
    
    st.title("📧 Email Parser")
    with st.expander("ℹ️ How to Use", expanded=False):
        fields = {
            field_name: field["description"] for field_name, field in EMAIL_SCHEMA["items"]["properties"].items()
        }
        field_string = "\n".join([f"- **{name}**: {desc}" for name, desc in fields.items()])
        readme = f"""
Parses raw unstructured text from Google Docs into structured email objects.

Each returned email object includes:
{field_string}
""".strip()
        st.write(readme)

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
                status = st.empty()
                tab1, tab2, tab3 = st.tabs(["📧 Pretty View", "📄 JSON", "📊 CSV"])
                
                # Create placeholders for each tab content
                with tab1:
                    pretty_placeholder = st.empty()
                with tab2:
                    json_placeholder = st.empty()
                with tab3:
                    csv_placeholder = st.empty()
                
                with raw_output_expander:
                    response_container = st.container()
                    stream_placeholder = response_container.empty()
                    
                    raw_response = ""
                    partial_emails = []
                    
                    for chunk in stream_response(input_text):
                        raw_response += chunk
                        stream_placeholder.code(raw_response, language="json")
                        
                        # Try to parse partial results
                        new_partial_emails = parse_response_partial(raw_response)
                        if new_partial_emails and len(new_partial_emails) > len(partial_emails):
                            partial_emails = new_partial_emails
                            status.text(f"Partially parsed {len(partial_emails)} email(s) so far...")
                            
                            # Update tabs with partial results
                            with pretty_placeholder.container():
                                for i, email in enumerate(partial_emails, 1):
                                    email_name = email.get('email_name', f'Email {i}')
                                    with st.expander(f"Email {i}: {email_name}", expanded=False):
                                        if (date := email.get("date")):
                                            st.write(f"**Date:** {date}")
                                        if (sender := email.get("sender")):
                                            st.write(f"**Sender:** {sender}")
                                        if (subject := email.get("subject")):
                                            st.write(f"**Subject:** {subject}")
                                        if (preview := email.get("preview")):
                                            st.write(f"**Preview:** {preview}")
                                        if (body := email.get("body")):
                                            st.write("**Body:**")
                                            st.text(body)
                            
                            json_placeholder.json(partial_emails)
                            
                            if partial_emails:
                                csv_data = emails_to_csv(partial_emails)
                                csv_placeholder.code(csv_data, language="csv", line_numbers=True)
            
            error_container = st.container()
            emails = parse_response_full(raw_response, error_container=error_container)
            
            # Final update with fully validated results
            status.success(f"Successfully parsed {len(emails)} email(s)!")
            
            with pretty_placeholder.container():
                for i, email in enumerate(emails, 1):
                    with st.expander(f"Email {i}: {email['email_name']}", expanded=False):
                        if (date := email.get("date")):
                            st.write(f"**Date:** {date}")
                        st.write(f"**Sender:** {email['sender']}")
                        st.write(f"**Subject:** {email['subject']}")
                        st.write(f"**Preview:** {email['preview']}")
                        st.write("**Body:**")
                        st.text(email["body"])
            
            json_placeholder.json(emails)
            
            csv_data = emails_to_csv(emails)
            csv_placeholder.code(csv_data, language="csv", line_numbers=True)

        except Exception as e:
            st.error(f"Error parsing emails: {e}")
            with raw_output_expander:
                response_container.error(f"**Final error:** {e}")


if __name__ == "__main__":
    main()
