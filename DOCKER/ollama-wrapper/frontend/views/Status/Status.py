import json
import streamlit as st

from lib.gateway import gateway_call
from lib.openapi import GATEWAY_OPENAPI_URL, OLLAMA_OPENAPI_URL
from lib.services import load_prompt_templates

from lib.openapi import EXTENDED

def render():

    health = gateway_call(EXTENDED.health)['raw']

    section_tabs = st.tabs(["Overview", "Health", "Recent prompts", "Status"])
    with section_tabs[0]:
        st.subheader("Overview")
        cols = st.columns(2)

        cols[0].metric(label="Gateway", value=health)
        cols[1].metric(label="Templates", value=len(load_prompt_templates()))

    with section_tabs[1]:
        st.subheader("Health")
        st.write(health)

    with section_tabs[2]:
        st.subheader("Recent prompts")
        logs = gateway_call(EXTENDED.prompts.recent)
        st.dataframe(logs)

    with section_tabs[3]:
        st.subheader("Status")
        st.write(f"Ollama: `{OLLAMA_OPENAPI_URL}`")
        st.write(f"Gateway: `{GATEWAY_OPENAPI_URL}`")
        try:
            v = gateway_call("/api/version")
            st.success(f"Ollama version: {v}")
        except Exception as e:
            st.error(f"Cannot reach Ollama: {e}")

        try:
            status = gateway_call(EXTENDED.monitoring_status)
            st.code(json.dumps(status, indent=2), language="json")
        except Exception as e:
            st.error(f"Extended status error: {e}")


if __name__ == "__main__":
    render()
