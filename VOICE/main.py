"""Dear Tomorrow: a voice chat with your future self."""
from llm import think
from stt import listen
from tts import speak
from voices import select_voice


def main():
    # Select a cloned voice before starting the conversation.
    voice_id = select_voice()

    print("Dear Tomorrow is ready. Say 'goodbye' to exit.")

    while True:
        # A network hiccup in any step shouldn't end the conversation.
        try:
            user_text = listen().strip()

            if not user_text:
                print("(Didn't catch that, try again.)")
                continue

            print(f"You: {user_text}")

            if "goodbye" in user_text.lower():
                speak("Take care of yourself. See you in the future!", voice_id)
                break

            reply = think(user_text)
            print(f"Dear Tomorrow: {reply}")
            speak(reply, voice_id)

        except Exception as e:
            print(f"(Connection problem: {type(e).__name__}: {e}. Please say that again.)")


if __name__ == "__main__":
    main()
