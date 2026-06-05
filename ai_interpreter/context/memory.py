from collections import deque
from typing import List, Optional

class ContextMemory:
    """
    ContextMemory: Maintains a rolling buffer of recent conversation turns.
    This provides context to the translation model, significantly improving
    accuracy for pronouns (e.g., 'it', 'he') and contextual references.
    """
    def __init__(self, max_history: int = 10):
        # Store tuples of (original_text, translated_text)
        self.history = deque(maxlen=max_history)
        self.max_history = max_history

    def add_turn(self, original: str, translation: Optional[str] = None):
        """Add a completed sentence/turn to the memory."""
        original = original.strip()
        if original:
            self.history.append((original, translation or ""))

    def get_context_prompt(self) -> str:
        """
        Returns the conversation history formatted as a context string.
        Can be prepended to the translation request.
        """
        if not self.history:
            return ""
        
        context_lines = []
        for orig, _ in self.history:
            context_lines.append(orig)
            
        context_text = " ".join(context_lines)
        return f"[Context: {context_text}] "

    def clear(self):
        """Clear memory (useful when a new session/meeting starts)."""
        self.history.clear()

# Global instance for quick access
global_context_memory = ContextMemory(max_history=10)
