import json

import streamlit as st

from lib.services import load_prompt_templates


def render():
    templates = load_prompt_templates()
    st.header("Prompt templates")
    df = []
    for template in templates:
        df.append(
            {
                "Name": template["name"],
                "Description": template.get("description", ""),
                "Messages": json.dumps(template.get("messages", [])),
            }
        )
    st.dataframe(df)


if __name__ == "__main__":
    render()
