
import re
import unittest
from unittest.mock import patch, MagicMock

# Assuming the chatbot logic is in a file named `chatbot.py`
from server.chatbot import get_agent_tools, SYSTEM_PROMPT, chat


class TestSocialMediaPoster(unittest.TestCase):
    def setUp(self):
        self.user_id = "test-user"
        self.groq_api_key = "test-groq-api-key"

    @patch("server.chatbot.post_quote_to_twitter")
    def test_post_to_twitter_intent(self, mock_post_quote_to_twitter):
        # Mock the tool to prevent actual API calls
        mock_post_quote_to_twitter.return_value = "Successfully posted to Twitter"

        # User message that should trigger the twitter post intent
        user_message = "Post this quote to Twitter: 'This is a test quote.'"

        # Run the chat function
        result = chat(
            user_message=user_message,
            groq_api_key=self.groq_api_key,
            user_id=self.user_id,
        )

        # Assert that the twitter post tool was called
        mock_post_quote_to_twitter.assert_called_once()
        self.assertIn("Successfully posted to Twitter", result["message"])

    @patch("server.chatbot.post_quote_to_facebook")
    def test_post_to_facebook_intent(self, mock_post_quote_to_facebook):
        # Mock the tool to prevent actual API calls
        mock_post_quote_to_facebook.return_value = "Successfully posted to Facebook"

        # User message that should trigger the facebook post intent
        user_message = "Post this quote to Facebook: 'This is a test quote.'"

        # Run the chat function
        result = chat(
            user_message=user_message,
            groq_api_key=self.groq_api_key,
            user_id=self.user_id,
        )

        # Assert that the facebook post tool was called
        mock_post_quote_to_facebook.assert_called_once()
        self.assertIn("Successfully posted to Facebook", result["message"])

    @patch("server.chatbot.post_quote_to_instagram")
    def test_post_to_instagram_intent(self, mock_post_quote_to_instagram):
        # Mock the tool to prevent actual API calls
        mock_post_quote_to_instagram.return_value = "Successfully posted to Instagram"

        # User message that should trigger the instagram post intent
        user_message = "Post this quote to Instagram: 'This is a test quote.'"

        # Run the chat function
        result = chat(
            user_message=user_message,
            groq_api_key=self.groq_api_key,
            user_id=self.user_id,
        )

        # Assert that the instagram post tool was called
        mock_post_quote_to_instagram.assert_called_once()
        self.assertIn("Successfully posted to Instagram", result["message"])


if __name__ == "__main__":
    unittest.main()
