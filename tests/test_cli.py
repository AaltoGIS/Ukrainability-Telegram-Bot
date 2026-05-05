from cryptography.fernet import Fernet


def test_cli_main_invokes_runtime_run(monkeypatch, tmp_path):
    from ukrainability_telegram_bot import cli, config, runtime

    fake_config = config.AppConfig(
        telegram_bot_token="token",
        encryption_key=Fernet.generate_key().decode("ascii"),
        user_hash_salt="salt",
        storage_dir=tmp_path,
        bot_errors_log=str(tmp_path / "bot_errors.log"),
        flow_control_log=str(tmp_path / "flow_control.log"),
        voice_retention_days=30,
        cleanup_interval_seconds=24 * 60 * 60,
    )
    called_with = {}

    monkeypatch.setattr(config.AppConfig, "from_env", classmethod(lambda cls: fake_config))
    monkeypatch.setattr(runtime, "run", lambda cfg: called_with.setdefault("cfg", cfg))

    cli.main()

    assert called_with["cfg"] is fake_config
