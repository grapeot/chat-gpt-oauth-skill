import io

from chat_gpt_oauth.http import post_sse


def test_stream_notifies_before_reading_next_event(monkeypatch):
    observed = []

    class Stream(io.BytesIO):
        def __next__(self):
            if self.tell() > 0:
                assert observed  # Callback has run before the second line is consumed.
            return super().__next__()

    raw = b'data: {"type":"response.output_text.delta","delta":"OK"}\n'
    raw += b'data: {"type":"response.completed","response":{}}\n'
    monkeypatch.setattr("chat_gpt_oauth.http.urlopen", lambda *a, **kw: Stream(raw))
    result = post_sse("https://example.invalid", body=b"{}", headers={}, on_event=observed.append)
    assert result == observed
    assert len(result) == 2
