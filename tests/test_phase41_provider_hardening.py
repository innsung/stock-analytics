from pathlib import Path


def test_phase41_env_template_and_gitignore_are_safe():
    env_example = Path('.env.example').read_text(encoding='utf-8')
    gitignore = Path('.gitignore').read_text(encoding='utf-8')
    requirements = Path('requirements.txt').read_text(encoding='utf-8')
    assert 'KRX_ID=' in env_example
    assert 'KRX_PW=' in env_example
    assert 'KRX_ID=YOUR_' not in env_example
    assert '.env' in gitignore
    assert '!.env.example' in gitignore
    assert 'pykrx>=1.2.8,<2' in requirements


def test_phase41_docs_use_single_line_windows_command():
    doc = Path('V3_2_1_HISTORICAL_DATA_PHASE4_1.md').read_text(encoding='utf-8')
    assert 'krx-provider-check-v321 --code 005930 --end 20260709' in doc
    assert 'acquire-historical-data-v321 --universe-csv' in doc
