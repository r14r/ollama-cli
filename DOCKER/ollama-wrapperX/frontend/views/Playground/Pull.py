import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple, Dict, Any

import streamlit as st

from lib.helper_ollama import helper


# ---------------------------------------------------------------------
# Safe parsing helpers
# ---------------------------------------------------------------------
def parse_phase_kv(phase: str) -> Dict[str, str]:
    """
    Parse a phase string like:
        "status='pulling 96c415656d37' completed=281382160 total=4683073184 digest='sha256:...'"
    into:
        {
            "status": "pulling 96c415656d37",
            "completed": "281382160",
            "total": "4683073184",
            "digest": "sha256:..."
        }

    This is intentionally defensive:
    - ignores tokens without '='
    - only splits once on '='
    - strips quotes from values
    """
    result: Dict[str, str] = {}

    if not phase:
        return result

    for token in phase.split():
        if "=" not in token:
            continue

        # split only once -> safe if value contains '='
        k, v = token.split("=", 1)

        # strip single/double quotes from value
        v = v.strip("'").strip('"')

        result[k] = v

    return result


def parse_completed_total_from_phase(phase: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Extract completed and total as integers from a phase string.

    Returns (completed, total) or (None, None) if not found / not parseable.
    """
    kv = parse_phase_kv(phase)

    def to_int_safe(val: Optional[str]) -> Optional[int]:
        if val is None:
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    completed = to_int_safe(kv.get("completed"))
    total = to_int_safe(kv.get("total"))

    return completed, total


def phase_from_chunk(chunk: Dict[str, Any]) -> str:
    """
    Human-readable phase label for the UI.

    You can customize this mapping if needed.
    """
    status = str(chunk.get("status", "")).strip()
    if status:
        return status
    return "running"


# ---------------------------------------------------------------------
# Shared pull state
# ---------------------------------------------------------------------
pull_state_lock = threading.Lock()
pull_state: Dict[str, Dict[str, Any]] = {}
# Structure per model:
# {
#   "status": "pending" | "running" | "done" | "error",
#   "phase": str,
#   "completed": int | None,
#   "total": int | None,
#   "error": str | None,
#   "last_chunk": dict | None,
# }


# ---------------------------------------------------------------------
# Background worker: real Ollama streaming pull
# ---------------------------------------------------------------------
def _pull_worker(model_name: str) -> None:
    """
    Runs in a background thread.
    Calls helper.models.pull(model_name, stream=True) and writes updates
    into pull_state. No Streamlit calls here.
    """
    global pull_state

    with pull_state_lock:
        pull_state[model_name] = {
            "status": "running",
            "phase": "starting",
            "completed": 0,
            "total": None,
            "error": None,
            "last_chunk": None,
        }

    try:
        for chunk in helper.models.pull(model_name, stream=True):
            # chunk might be dict or string; normalize
            if not isinstance(chunk, dict):
                try:
                    chunk = json.loads(str(chunk))
                except Exception:
                    # fall back: just wrap as status text
                    chunk = {"status": str(chunk)}

            # Short phase label for UI
            phase_text = phase_from_chunk(chunk)

            # Try to use explicit completed/total if present
            completed = chunk.get("completed")
            total = chunk.get("total")

            # Some setups encode bytes in a status-like string;
            # use the *raw* representation for parsing
            raw_text = str(chunk)

            # Only parse from raw if missing/zero
            if (not completed) or (not total):
                parsed_completed, parsed_total = parse_completed_total_from_phase(raw_text)
                if parsed_completed is not None:
                    completed = parsed_completed
                if parsed_total is not None:
                    total = parsed_total

            error = chunk.get("error")

            with pull_state_lock:
                job = pull_state[model_name]
                job["phase"] = phase_text
                job["last_chunk"] = chunk

                if completed is not None:
                    job["completed"] = completed
                if total is not None:
                    job["total"] = total

                if error:
                    job["status"] = "error"
                    job["error"] = str(error)
                    break

                # Many Ollama streams end with a 'success' status
                if phase_text.lower().startswith("success"):
                    job["status"] = "done"

        # If we exited the loop without explicit success/error, mark as done
        with pull_state_lock:
            job = pull_state[model_name]
            if job["status"] == "running":
                job["status"] = "done"
                if job["phase"] == "starting":
                    job["phase"] = "finished"

    except Exception as exc:
        with pull_state_lock:
            job = pull_state.get(model_name, {})
            job["status"] = "error"
            job["error"] = str(exc)
            pull_state[model_name] = job


# ---------------------------------------------------------------------
# Streamlit-facing function: progress bars and UI
# ---------------------------------------------------------------------
def pull_models_with_progress(model_names: list[str], max_workers: Optional[int] = None) -> None:
    """
    Pull all given models in parallel using real streaming and show
    per-model progress bars. Progress bar width is strictly based on
    completed / total (from phase parsing if necessary).
    """
    if not model_names:
        st.info("No models to pull.")
        return

    st.subheader("Pulling Ollama models (streaming)")

    global pull_state
    with pull_state_lock:
        pull_state = {
            name: {
                "status": "pending",
                "phase": "queued",
                "completed": 0,
                "total": None,
                "error": None,
                "last_chunk": None,
            }
            for name in model_names
        }

    # One progress bar per model
    bars: Dict[str, Any] = {
        name: st.progress(0.0, text=f"{name}: queued")
        for name in model_names
    }

    # Optional debug expander
    expander = st.expander("Debug: last chunk per model", expanded=False)
    debug_placeholder = expander.empty()

    if max_workers is None:
        max_workers = min(4, len(model_names))

    # Start background workers
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for name in model_names:
            executor.submit(_pull_worker, name)

        # Main UI loop
        while True:
            time.sleep(0.1)

            with pull_state_lock:
                snapshot = {k: v.copy() for k, v in pull_state.items()}

            all_done = True

            for name in model_names:
                info = snapshot[name]
                status = info["status"]
                phase = info["phase"]
                error = info["error"]

                completed = info["completed"]
                total = info["total"]

                if status in ("pending", "running"):
                    all_done = False

                if status == "error":
                    frac = 0.0
                    label = f"{name}: ERROR – {phase}"
                    bars[name].progress(frac, text=label)
                    if error:
                        st.error(f"Error pulling '{name}': {error}")
                    continue

                # Strict: width from completed / total only
                if total is not None and total > 0 and completed is not None:
                    frac = max(0.0, min(completed / total, 1.0))
                    mb_done = completed / 1_048_576
                    mb_total = total / 1_048_576
                    label = f"{name}: {phase} ({mb_done:.1f} / {mb_total:.1f} MB)"
                else:
                    # total not known yet -> keep at 0%, show phase
                    frac = 0.0
                    label = f"{name}: {phase} (preparing…)"

                bars[name].progress(frac, text=label)

            # Debug: last chunks
            with pull_state_lock:
                last_chunks = {
                    model: pull_state[model]["last_chunk"]
                    for model in model_names
                }
            debug_placeholder.json(last_chunks)

            if all_done:
                break

    # Finalize bars
    with pull_state_lock:
        final_snapshot = {k: v.copy() for k, v in pull_state.items()}

    for name in model_names:
        info = final_snapshot[name]
        if info["status"] == "done":
            bars[name].progress(1.0, text=f"{name}: success")
        elif info["status"] == "error":
            bars[name].progress(0.0, text=f"{name}: error")


# ---------------------------------------------------------------------
# Example Streamlit UI entry point
# ---------------------------------------------------------------------
def main() -> None:
    st.title("Ollama Model Puller – Streaming with Safe Phase Parsing")

    # Replace with helper.models.list() or similar in your code
    available_models = ["llama3", "phi4", "gemma2:9b", "minicpm-v:8b"]

    selected = st.multiselect(
        "Select models to pull:",
        options=available_models,
        default=available_models,
    )

    if st.button("Pull selected models"):
        pull_models_with_progress(selected)


if __name__ == "__main__":
    main()
