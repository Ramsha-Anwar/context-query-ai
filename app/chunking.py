def chunk_text(text: str, size_tokens: int = 500, overlap_tokens: int = 50) -> list[tuple[str, int]]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i:i + size_tokens]
        chunks.append((" ".join(chunk_words), len(chunk_words)))
        i += size_tokens - overlap_tokens
    return chunks