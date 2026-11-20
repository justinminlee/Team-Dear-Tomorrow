"""Let the user pick which cloned voice to use."""
from config import VOICES


# Allow the user to select a cloned voice
def select_voice():
    names = list(VOICES.keys())

    print("\nSelect your voice:")

    for i, name in enumerate(names, start=1):
        print(f"{i}. {name}")

    while True:
        choice = input("Select a number: ")

        if choice.isdigit() and 1 <= int(choice) <= len(names):
            return VOICES[names[int(choice) - 1]]

        print("Invalid choice. Please try again.")
