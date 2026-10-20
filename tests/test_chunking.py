from app.chunking import chunk_text

def test_chunk_text_basic():
    text = "word " * 1000
    chunks = chunk_text(text, size_tokens=500, overlap_tokens=50)
    assert len(chunks) == 3
    # First chunk should have 500 words
    assert chunks[0][1] == 500
    # Second chunk should overlap by 50 words (starts at word 450)
    assert chunks[1][1] == 500

def test_chunk_text_infinite_loop_prevention():
    text = "word " * 1000
    # This would cause an infinite loop if we didn't fix the math
    chunks = chunk_text(text, size_tokens=500, overlap_tokens=600)
    assert len(chunks) > 0 # It survived!

def test_chunk_text_empty():
    assert chunk_text("") == []