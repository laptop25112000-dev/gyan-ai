import unittest

from gyaan.router import route_question


class RouterTest(unittest.TestCase):
    def test_latest_question_uses_web(self):
        decision = route_question("What is the latest AI news?")
        self.assertTrue(decision.needs_web)
        self.assertIn("source_checker", decision.model_roles)

    def test_code_question_uses_coder(self):
        decision = route_question("Write Python code")
        self.assertFalse(decision.needs_web)
        self.assertIn("coder", decision.model_roles)


if __name__ == "__main__":
    unittest.main()
