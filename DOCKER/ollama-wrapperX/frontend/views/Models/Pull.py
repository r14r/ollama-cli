import streamlit as st

from lib.helper_ollama import helper
from lib.helper_streamlit import models_view_tree


def render() -> None:
    st.subheader("Pull Models")

    available_models = helper.get_available_models_with_details()
    available_categories = helper.get_available_categories()

    col_by_tools, col_by_state = st.columns([1, 1])

    with col_by_state:
        filter_state = st.segmented_control(
            "Filter by State", ["all", "installed", "not installed"],
        )

    with col_by_tools:
        filter_categories = st.segmented_control(
            "Filter by Category", available_categories, selection_mode="multi"
        )

    filtered_models_by_state = available_models.get_by_state(filter_state)
    filtered_models = filtered_models_by_state.get_by_categories(filter_categories)

    with st.expander("Select Models", expanded=True):
        selected_models = models_view_tree(models=filtered_models, label=f"Models: {len(filtered_models)}", expanded=True)

    st.write(f"#### Select model(s) to pull: {selected_models}")

    if st.button("Pull all models"):
        for model in selected_models:
            st.write(f"- {model}")
            response = helper.models.pull(model, stream=False)
            st.write(f"Pulled model {model}")

        st.success("All selected models have been pulled.")


if __name__ == "__main__":
    render()
