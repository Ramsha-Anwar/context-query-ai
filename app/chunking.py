def chunk_text(text: str, size_tokens: int = 500, overlap_tokens: int = 50) -> list[tuple[str, int]]:
    """Splits text into chunks of `size_tokens` with `overlap_tokens` overlap."""
    if not text.strip():
        return []
        
    # Safety check: overlap must be strictly less than size
    if overlap_tokens >= size_tokens:
        overlap_tokens = size_tokens - 1
        
    words = text.split()
    chunks = []
    step = size_tokens - overlap_tokens
    i = 0
    
    while i < len(words):
        chunk_words = words[i:i + size_tokens]
        chunks.append((" ".join(chunk_words), len(chunk_words)))
        i += step
        
    return chunks