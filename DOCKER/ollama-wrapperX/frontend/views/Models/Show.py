import streamlit as st

from lib.helper_ollama import helper


def render() -> None:
    st.subheader("Show Model")

    installed_names = helper.get_installed_models_names()
    installed_models = helper.get_installed_models_with_details()
    if installed_names:
        model_name = st.selectbox("Select a model", installed_names)
        model_obj = installed_models.initial_models(model_name)
        description = model_obj.show().json() if model_obj else {}

        st.json(description)
    else:
        st.info("No installed models available.")


if __name__ == "__main__":
    render()
