from __future__ import annotations

from typing import Any, Mapping

import logging
import os
import pytest

from lib.helper_ollama.client import ChatResponse, GenerateResponse
from lib.helper_ollama.model import Model
from lib.helper_ollama.types import ResponseState, RESPONSESTATES
from tests.lib.helper_ollama.conftest import (
    OLLAMA_TEST_PREINSTALLED_MODEL,
    OLLAMA_TEST_UNINSTALLED_MODEL,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# -----------
# Testing Ollama Base Functions
#  create      Create a model
#  show        Show information for a model
#  run         Run a model
#  stop        Stop a running model
#  pull        Pull a model from a registry
#  push        Push a model to a registry
#  signin      Sign in to ollama.com
#  signout     Sign out from ollama.com
#  list        List models
#  ps          List running models
#  cp          Copy a model
# rm          Remove a model


#
def test_base_show(model: Model):
    response = model.show()

    assert isinstance(response, ResponseState)
    assert response.state == RESPONSESTATES.ERROR


@pytest.mark.with_model_installed
def test_base_show_installed_model() -> None:
    r = Model(OLLAMA_TEST_PREINSTALLED_MODEL).show()

    assert isinstance(r, ResponseState)
    assert r.state == RESPONSESTATES.OK
    assert r.response.modelinfo["general.architecture"] == "phi3"
    assert r.response.modelinfo["general.basename"] == "Phi-4"


@pytest.mark.with_model_uninstalled
def test_base_show_uninstalled_model() -> None:
    r = Model(OLLAMA_TEST_UNINSTALLED_MODEL).show()

    assert isinstance(r, ResponseState)
    assert r.state == RESPONSESTATES.ERROR
    assert "not found" in r.message


@pytest.mark.with_model_installed
def test_base_pull_installed_model() -> None:
    model = OLLAMA_TEST_PREINSTALLED_MODEL

    logger.info("test_base_pull start")

    response = Model(model).pull()

    assert isinstance(response, ResponseState)
    logger.info("test_base_pull end")
    logger.info("test_model_pull_returns_state end")


@pytest.mark.with_model_uninstalled
def test_base_pull_uninstalled_model() -> None:
    model = OLLAMA_TEST_UNINSTALLED_MODEL

    logger.info("test_base_pull start")

    response = Model(model).pull()

    assert isinstance(response, ResponseState)
    logger.info("test_base_pull end")
    logger.info("test_model_pull_returns_state end")


def test_base_chat(model: Model) -> None:
    logger.info("test_base_chat start")
    messages = [
        {"role": "user", "content": "what is your model name. answer in one sentence"}
    ]

    r = model.chat(messages=messages, temperature=0)

    assert isinstance(r, ResponseState)
    logger.info("test_base_chat assert: correct return type")

    assert r.state == RESPONSESTATES.OK
    logger.info("test_base_chat assert: correct response state")

    assert isinstance(r.response, ChatResponse)
    logger.info("test_base_chat assert: correct response type")

    #
    result_content = r.response.message.content
    except_content = "My model name is Phi developed by Microsoft."

    assert result_content == except_content
    logger.info("test_base_chat assert: correct response content")

    logger.info("test_base_chat end")


def test_base_generate(model: Model) -> None:
    r = model.generate(
        prompt="what is your model name. answer in one sentence", temperature=0
    )

    assert isinstance(r, ResponseState)
    assert r.state == RESPONSESTATES.OK
    assert isinstance(r.response, GenerateResponse)
    assert r.response.response == "My model name is Phi developed by Microsoft."


@pytest.mark.with_model_installed
def test_base_delete() -> None:
    logger.info("test_base_delete start: delete {OLLAMA_TEST_PREINSTALLED_MODEL}")
    r = Model(OLLAMA_TEST_PREINSTALLED_MODEL).delete()

    assert isinstance(r, ResponseState)
    assert r.state in (RESPONSESTATES.OK, RESPONSESTATES.ERROR)


def test_base_copy() -> None:
    r = Model(OLLAMA_TEST_PREINSTALLED_MODEL).copy("copy")

    assert isinstance(r, ResponseState)


def test_base_create() -> None:
    modelfile = f"FROM {OLLAMA_TEST_PREINSTALLED_MODEL}\nPARAM temperature 0.0"
    state = Model().create(name="test_model", modelfile=modelfile, stream=False)

    assert isinstance(state, ResponseState)
