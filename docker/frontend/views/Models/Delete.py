import streamlit as st
from lib.helper_ollama import helper, Model
from lib.helper_streamlit import models_view_tree

def render() -> None:
    st.subheader("Delete Models")

    #
    if "installed_models" not in st.session_state:
        st.session_state.installed_models = helper.get_installed_models_with_details()

    installed_models = st.session_state.installed_models

    #
    selected_models = models_view_tree(
        models=installed_models,
        label=f"Models: {len(installed_models)}",
        expanded=True,
        with_state=False,
        with_categories=False,
        with_description=False,

    )

    # delete_models = selected_models

    st.write(f"#### Select model(s) to delete: {selected_models}")

    if st.button("Delete selected models"):
        for model in selected_models:
            st.info(f"Deleting model: {model}")
            Model(model).delete()

if __name__ == "__main__":
    render()
