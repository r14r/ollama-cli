import streamlit as st

from lib.helper_ollama import helper
from lib.helper_streamlit import models_view_tree


def render() -> None:
    st.subheader("List Models")

    if "available_models" not in st.session_state:
         st.session_state.available_models = helper.get_available_models_with_details()

    available_models = st.session_state.available_models

    available_categories = helper.get_available_categories()

    col_by_tools, col_by_state = st.columns([1, 1])

    with col_by_state:
        filter_state = st.segmented_control(
            "Filter by State", ["all", "installed", "not installed"], selection_mode="single"
        )

    with col_by_tools:
        filter_categories = st.segmented_control(
            "Filter by Category", available_categories, selection_mode="multi"
        )

    #st.write("Refresh")
    #if st.button("Refresh"):
    #    helper.refresh()

    filtered_models_by_state = available_models.get_by_state(filter_state)
    filtered_models = filtered_models_by_state.get_by_categories(filter_categories)

    models_view_tree(models=filtered_models, label=f"Models: {len(filtered_models)}", expanded=True)

if __name__ == "__main__":
    render()
