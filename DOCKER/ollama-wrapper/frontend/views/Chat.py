import streamlit as st

from lib.gateway import gateway_call
from lib.services import load_prompt_templates

from lib.openapi import EXTENDED

def render(templates) -> None:
    st.header("Integrated chat")

    target_options = ["Native Ollama", "Gateway default"]
    prompt = st.text_area("User message")
    template_names = [t["name"] for t in templates]
    selected_template = st.selectbox("Apply template", template_names or [""], index=0)

    initial_message = []
    if selected_template:
        template = next((t for t in templates if t["name"] == selected_template), None)
        if template:
            initial_message = template.get("messages", [])

    if st.button("Send") and prompt.strip():
        body = {"model": "llama3", "messages": initial_message + [{"role": "user", "content": prompt}], "target": "gateway"}
        try:
            response = gateway_call(EXTENDED.chat, method="POST", payload=body)
            st.json(response.json())
        except Exception as exc:
            st.error(f"Chat failed: {exc}")


if __name__ == "__main__":
    templates = load_prompt_templates()
    render(templates)
