"""The privacy:local guard must catch excerpts and reformatted copies of a local
note, not only the whole note pasted verbatim."""

import pytest
from conftest import reply

from halo.models.client import PrivacyViolationError

NOTE = """Monthly salary: 5,20,000 rupees, credited on the 28th.
Savings target is 40 percent of take-home pay."""


def _client(make_client):
    return make_client(reply("ok"), local_texts=lambda: [NOTE])


async def _send(client, text: str) -> None:
    await client.call("nano", [{"role": "user", "content": text}])


@pytest.mark.parametrize(
    "leak",
    [
        NOTE,  # the whole note
        "plan my trip, note: Monthly salary: 5,20,000 rupees, credited on the 28th.",  # one line
        "context: SAVINGS TARGET IS 40 PERCENT OF TAKE-HOME PAY",  # case
        "monthly   salary:\n5,20,000   rupees, credited on the\n28th.",  # whitespace and newlines
        "my salary is 'Monthly salary: 5,20,000 rupees' ok",  # a fragment of one line
    ],
)
async def test_text_taken_from_a_local_note_is_blocked(make_client, leak: str) -> None:
    client, transport, _ = _client(make_client)
    with pytest.raises(PrivacyViolationError):
        await _send(client, leak)
    assert transport.calls == []


@pytest.mark.parametrize(
    "fine",
    [
        "plan a four day trip to Goa in December",
        "what is a good savings rate?",  # shares words with the note but copies nothing
        "salary",  # a single common word
    ],
)
async def test_unrelated_text_is_allowed(make_client, fine: str) -> None:
    client, transport, _ = _client(make_client)
    await _send(client, fine)
    assert len(transport.calls) == 1


async def test_very_short_local_notes_do_not_block_everything(make_client) -> None:
    client, transport, _ = make_client(
        reply("ok"), local_texts=lambda: ["a", "ok", " "]
    )
    await _send(client, "can you plan a trip? ok a")
    assert len(transport.calls) == 1


async def test_text_in_any_message_not_just_the_last_is_checked(make_client) -> None:
    client, transport, _ = _client(make_client)
    messages = [
        {"role": "system", "content": "Savings target is 40 percent of take-home pay."},
        {"role": "user", "content": "hello"},
    ]
    with pytest.raises(PrivacyViolationError):
        await client.call("nano", messages)
    assert transport.calls == []
