import streamlit as st

from lib.openapi import EXTENDED
from lib.services import gateway_call


def render():
    section_tabs = st.tabs(["Gateway"])
    with section_tabs[0]:
        st.subheader("Gateway health")
        st.json(gateway_call(EXTENDED.monitoring_status))


if __name__ == "__main__":
    render()
