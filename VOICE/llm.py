"""Talk to the LLM and keep the conversation history."""
import httpx

from config import API_KEY, MODEL, SYSTEM_PROMPT

messages = [{"role": "system", "content": SYSTEM_PROMPT}]

# One shared client keeps the connection open between turns (no new TLS handshake each time),
# and retries the connection up to 3 times if the network drops for a moment.
llm_client = httpx.Client(
    base_url="https://llm-gateway.assemblyai.com",
    headers={"Authorization": API_KEY},
    timeout=httpx.Timeout(30, connect=10),
    transport=httpx.HTTPTransport(retries=3),
)


# Send the user's input and conversation history to the LLM and return the generated response.
def think(user_text):
    """Send the conversation to the LLM and return its reply."""
    messages.append({"role": "user", "content": user_text})

    try:
        response = llm_client.post(
            "/v1/chat/completions",
            json={"model": MODEL, "messages": messages, "max_tokens": 200},
        )
        response.raise_for_status()
        reply = response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        messages.pop()  # drop the unanswered question so the history stays clean
        raise

    messages.append({"role": "assistant", "content": reply})

    return reply
