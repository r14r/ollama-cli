"""Example helpers showing how to wire LangChain / LangGraph into the gateway."""

import os
from infra.shared.sdk.python.gateway_sdk import GatewayClient

from lib.config import get



def langchain_example(topic: str) -> str:
    try:
        from langchain.chat_models import ChatOpenAI
        from langchain.chains import LLMChain
        from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
    except ImportError:  # pragma: no cover - optional dependency
        raise ImportError("Install langchain to use this helper")

    llm = ChatOpenAI(
        temperature=0,
        openai_api_base=f"{get_gateway_url()}/v1",
        openai_api_key="",
    )
    prompt = ChatPromptTemplate.from_messages([
        HumanMessagePromptTemplate(prompt="Respond concisely about {topic}"),
    ])
    chain = LLMChain(llm=llm, prompt=prompt)
    return chain.run(topic=topic)


def langgraph_example(prompt: str) -> str:
    try:
        from langgraph import LangGraph
    except ImportError:  # pragma: no cover - optional dependency
        raise ImportError("Install langgraph to use this helper")

    client = GatewayClient(get_gateway_url())
    graph = LangGraph()
    graph.chain("gateway_chat", client.chat)
    return graph.execute("gateway_chat", prompt=prompt)
