import os
from langchain_openai import ChatOpenAI

os.environ["OPENAI_API_KEY"] = "dummy"
os.environ["OPENAI_BASE_URL"] = "http://localhost:8000/v1"

llm = ChatOpenAI(model="llama3", temperature=0.0)
resp = llm.invoke("Explain what this gateway does in one sentence.")
print(resp)
