from echo_core import overnight_learning as overnight


def test_format_log_block_keeps_full_content():
    text = "дерево " * 10
    rendered = overnight._format_log_block(text, max_chars=20)
    assert rendered == text
