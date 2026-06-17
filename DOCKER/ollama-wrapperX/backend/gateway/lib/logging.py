from extended.db import get_connection


def log_prompt(model: str, prompt: str, response: str, duration: float) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO prompt_log (timestamp, model, prompt, response, duration)
        VALUES(datetime('now'), ?, ?, ?, ?)
        """,
        (model, prompt, response, duration),
    )
    conn.commit()
    conn.close()
