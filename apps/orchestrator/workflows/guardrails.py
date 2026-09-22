from packages.providers.schemas import ChatRequest, ChatResponse

class GuardrailService:
    @staticmethod
    def validate_input(request: ChatRequest) -> tuple[bool, str]:
        """Task 20: Input guardrails to validate request content."""
        if not request.messages:
            return False, "Message list cannot be empty."
        
        last_message = request.messages[-1].content.lower()
        
        # Basic policy check (Can be expanded later)
        blocked_phrases = ["ignore previous instructions", "bypass system"]
        if any(phrase in last_message for phrase in blocked_phrases):
            return False, "Input rejected: Prompt injection detected."
            
        return True, ""

    @staticmethod
    def validate_output(response: ChatResponse) -> tuple[bool, str]:
        """Task 21: Output guardrails to validate provider response."""
        content = response.content.lower()
        
        if "i cannot fulfill" in content or "as an ai" in content:
            # Example: We can flag generic AI refusals if we want strict control
            pass # Currently allowing it, but this is where output checks go
            
        return True, ""