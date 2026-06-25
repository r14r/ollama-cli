import streamlit as st

pages = {
    "Models": [
        st.Page("views/Models/List.py", title="List", icon="📋", url_path="models_list"),
        st.Page("views/Models/Show.py", title="Show", icon="👁️", url_path="models_show"),
        st.Page("views/Models/Pull.py", title="Pull", icon="⬇️", url_path="models_pull"),
        st.Page("views/Models/Delete.py", title="Delete", icon="🗑️", url_path="models_delete"),
    ],
    "Chat": [
        st.Page("views/Chat/Chat.py", title="Chat Intro", icon="💬", url_path="chat_intro"),
    ],
    "Status": [
        st.Page("views/Status/Status.py", title="Status", icon="📈", url_path="status_intro"),
    ],
    "Monitoring": [
        st.Page("views/Monitoring/Monitoring.py", title="Monitoring", icon="📊", url_path="monitoring_intro"),
    ],
    "Prompts": [
        st.Page("views/Prompts/Prompts.py", title="Prompts", icon="💬", url_path="prompts_intro"),
    ],
    "Templates": [
        st.Page("views/Templates/Templates.py", title="Templates", icon="📐", url_path="templates_intro"),
    ],
    "Playground": [
        st.Page("views/Playground/Components.py", title="Introduction", icon="🎡", url_path="playground_intro"),
        st.Page("views/Playground/Pull.py", title="Pull", icon="🎡", url_path="playground_pull"),
    ],

    "API Test": [
        st.Page("views/API-Test/API-Tests.py", title="API Tests", icon="🧪", url_path="api_tests"),
    ],
}

pg = st.navigation(pages)
pg.run()
