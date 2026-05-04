from types import SimpleNamespace

from ukrainability_telegram_bot import keyboards


class FakeButton:
    def __init__(self, *, text, callback_data):
        self.text = text
        self.callback_data = callback_data


class FakeMarkup:
    def __init__(self):
        self.rows = []

    def add(self, button):
        self.rows.append(button)


def test_create_inline_keyboard_adds_options_and_done(monkeypatch):
    monkeypatch.setattr(
        keyboards,
        "types",
        SimpleNamespace(InlineKeyboardMarkup=FakeMarkup, InlineKeyboardButton=FakeButton),
    )

    keyboard = keyboards.create_inline_keyboard(["One", "Two"], "choice")

    assert [button.text for button in keyboard.rows] == ["One", "Two", "Done"]
    assert [button.callback_data for button in keyboard.rows] == [
        "choice_0",
        "choice_1",
        "choice_done",
    ]


def test_create_inline_keyboard_can_skip_done_for_single_select(monkeypatch):
    monkeypatch.setattr(
        keyboards,
        "types",
        SimpleNamespace(InlineKeyboardMarkup=FakeMarkup, InlineKeyboardButton=FakeButton),
    )

    keyboard = keyboards.create_inline_keyboard(["One"], "choice", single_select=True)

    assert [button.callback_data for button in keyboard.rows] == ["choice_0"]
