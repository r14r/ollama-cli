import streamlit as st
from lib.helper_ollama import helper
from lib.helper_streamlit import models2tree, models_view_tree


def render():
    st.subheader("Components Playground")

    available_components = [
        model for model in helper.get_available_models_with_details()
    ]
    available_components_tree = models2tree(available_components)

    models_view_tree(available_components_tree, expanded=True)


if __name__ == "__main__":
    render()
