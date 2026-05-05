from ukrainability_telegram_bot import bot, runtime


def test_bot_module_reexports_runtime_entrypoints():
    assert bot.configure_runtime is runtime.configure_runtime
    assert bot.run is runtime.run
    assert bot.__all__ == ["configure_runtime", "run"]
