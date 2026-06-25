import json

import streamlit as st

from lib.openapi import EXTENDED
from lib.services import gateway_call, safe_json


def render():
    section_tabs = st.tabs(["Templates", "History"])
    with section_tabs[0]:
        st.subheader("Create / update template")
        with st.form("template_form"):
            name = st.text_input("Template name")
            description = st.text_input("Description")
            example_message = st.text_area(
                "Base message (JSON array)",
                value='[{"role": "system", "content": "You are helpful"}]',
            )
            if st.form_submit_button("Save template"):
                try:
                    payload = {
                        "name": name,
                        "description": description,
                        "messages": json.loads(example_message),
                    }
                    gateway_call(EXTENDED.prompts.root, method="POST", payload=payload)
                    st.success("Template saved")
                except Exception as exc:
                    st.error(f"Saving template failed: {exc}")
    with section_tabs[1]:
        st.subheader("Prompt log")

        prompts_recent = gateway_call(EXTENDED.prompts.recent)
        st.dataframe(prompts_recent)


if __name__ == "__main__":
    render()
