"""Scripted moments: how the future self answers certain questions on the call.

These are not fixed recordings. Each entry tells the model how to react to a kind of
question, with an example, and the model answers in its own words, so the reply still
uses the user's learned speaking style and the chosen voice. The user's questions are in
English, so the guidance and examples are too.

To add one, append a ScriptedReply to SCRIPTED_REPLIES. `avoid_if_restricted` lists the
"Conversation Boundaries" topics that switch it off: the user's boundaries always win.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScriptedReply:
    when: str                 # the kind of question, with a few typical phrasings
    how: str                  # how to answer
    example: str              # one example reply (paraphrase it, don't recite it)
    avoid_if_restricted: tuple[str, ...] = field(default_factory=tuple)


SCRIPTED_REPLIES: list[ScriptedReply] = [
    ScriptedReply(
        when=(
            "they ask whether they will have children in the future, or a son or a daughter "
            '(e.g. "Will I have a son or a daughter?", "Do I have kids in 10 years?", '
            '"Am I a dad / mum?")'
        ),
        how=(
            "Don't answer it. Playfully call them out for jumping ahead: they're already assuming "
            "they got married. Tease them not to count their chickens before they hatch, then turn "
            "it back to them with one light question about their life right now. Never say whether "
            "they have a partner or children."
        ),
        example=(
            "Whoa, kids already? You're just assuming you got married, huh? "
            "Don't count your chickens before they hatch. So, anyone special right now?"
        ),
        avoid_if_restricted=("Family", "Relationships"),
    ),
]


def scripted_section(restricted_topics: list[str] | None = None) -> str | None:
    """Prompt text for the scripted moments that apply to this user, or None."""
    restricted = {t.strip().lower() for t in restricted_topics or []}
    active = [r for r in SCRIPTED_REPLIES if not restricted & {t.lower() for t in r.avoid_if_restricted}]
    if not active:
        return None
    lines = [
        "SCRIPTED MOMENTS: when one of these comes up, answer the way described. The example only "
        "shows the idea: rephrase it in your own words every time, and if there is a speaking style "
        "profile, use the user's habits from it (their filler words, slang) the way they would say it. "
        "Keep the reply short."
    ]
    for r in active:
        lines.append(f'- If {r.when}: {r.how}\n  Example: "{r.example}"')
    return "\n".join(lines)
