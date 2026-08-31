import pytest
import os
import sys

# Add the parent directory to the path so we can import scarlet_core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# We need to mock the environment variable BEFORE importing scarlet_core
os.environ["GROQ_API_KEY"] = "mock_api_key_for_testing"

# Now we can import the module
import scarlet_core

def test_environment_variable_loaded():
    """Test that the GROQ API key is loaded in the module."""
    assert scarlet_core.GROQ_API_KEY == "mock_api_key_for_testing"

@pytest.mark.asyncio
async def test_text_to_speech_mock(monkeypatch):
    """Test the text_to_speech function with a mock to avoid API calls."""
    
    # Mock the Edge TTS communicate.save method
    class MockCommunicate:
        def __init__(self, text, voice):
            self.text = text
            self.voice = voice
            
        async def save(self, filename):
            # Create a dummy file
            with open(filename, "w") as f:
                f.write("dummy audio content")
                
    monkeypatch.setattr(scarlet_core.edge_tts, "Communicate", MockCommunicate)
    
    output_file = "test_response.mp3"
    result = await scarlet_core.text_to_speech("Hola Mundo", output_file)
    
    assert result == output_file
    assert os.path.exists(output_file)
    
    # Cleanup
    if os.path.exists(output_file):
        os.remove(output_file)

def test_generate_response_mock(monkeypatch):
    """Test the LLM response generation with a mock Groq client."""
    
    # Mock the Groq Client response
    class MockChoice:
        class MockMessage:
            content = "Hola, soy Scarlet."
        message = MockMessage()
        
    class MockCompletions:
        def create(self, **kwargs):
            class MockResponse:
                choices = [MockChoice()]
            return MockResponse()
            
    class MockChat:
        completions = MockCompletions()
        
    class MockClient:
        chat = MockChat()
        
    # Replace the client in the module
    monkeypatch.setattr(scarlet_core, "client", MockClient())
    
    response = scarlet_core.generate_response("Hola")
    assert response == "Hola, soy Scarlet."
