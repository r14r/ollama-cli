import streamlit as st

from lib.services import admin_call, fetch_models, gateway_call, stream_response


def render() -> None:
    st.header("Model management")
    models = fetch_models()
    section_tabs = st.tabs(["Overview", "List", "Info", "Pull", "Remove", "Create", "Copy"])

    with section_tabs[0]:
        st.subheader("Overview")
        cols = st.columns(3)

    with section_tabs[1]:
        st.subheader("Installed models")
        if not models:
            st.info("No models installed.")
        else:
            for m in models:
                st.markdown(
                    f"- `{m.get('name')}` ({m.get('family') or m.get('details', {}).get('family')})"
                )
    with section_tabs[2]:
        st.subheader("Model info")
        model_name = st.selectbox(
            "Model to show", [m["name"] for m in models] or [""], index=0
        )
        if st.button("Show details"):
            if model_name:
                info = gateway_call(f"/extended/models/show/{model_name}")
                st.code(info.json(), language="json")
            else:
                st.warning("Pick a model first.")
    with section_tabs[3]:
        st.subheader("Pull model")
        with st.form("models_pull"):
            model_name = st.text_input("Model name", value="llama3")
            stream = st.checkbox("Stream logs", value=True)
            if st.form_submit_button("Pull"):
                resp = admin_call(
                    "/models/pull",
                    method="POST",
                    payload={"model": model_name, "stream": stream},
                    stream=stream,
                )
                if stream:
                    buffer = st.empty()
                    stream_response(resp, buffer)
                else:
                    st.code(resp.text, language="json")

    with section_tabs[4]:
        st.subheader("Remove model")
        with st.form("models_remove"):
            target = st.text_input("Model name")
            if st.form_submit_button("Remove"):
                admin_call("/models/remove", method="POST", payload={"model": target})
                st.success(f"Removed {target}")

    with section_tabs[5]:
        st.subheader("Create model")
        with st.form("models_create"):
            name = st.text_input("New model name", value="my-llama3")
            modelfile = st.text_area("Modelfile content", value="FROM llama3\n")
            stream = st.checkbox("Stream logs", value=True)
            if st.form_submit_button("Create"):
                resp = admin_call(
                    "/models/create",
                    method="POST",
                    payload={"name": name, "modelfile": modelfile, "stream": stream},
                    stream=stream,
                )
                if stream:
                    buffer = st.empty()
                    stream_response(resp, buffer)
                else:
                    st.code(resp.text, language="json")
    with section_tabs[6]:
        st.subheader("Copy model")
        with st.form("models_copy"):
            source = st.text_input("Source model name")
            destination = st.text_input("Destination model name")
            if st.form_submit_button("Copy"):
                resp = admin_call(
                    "/models/copy",
                    method="POST",
                    payload={"source": source, "destination": destination},
                )
                st.code(resp.text, language="json")


if __name__ == "__main__":
    render()
