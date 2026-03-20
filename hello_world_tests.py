import unittest
from hello_world import greet, display_info

class TestHelloWorld(unittest.TestCase):
    
    def test_greet(self):
        result = greet()
        self.assertEqual(result, "Hello, World!")
        print("test_greet PASSED")
    
    def test_display_info(self):
        info = display_info()
        self.assertIn("message", info)
        self.assertIn("platform", info)
        self.assertIn("python_version", info)
        self.assertIn("timestamp", info)
        print("test_display_info PASSED")
    
    def test_message_content(self):
        info = display_info()
        self.assertIn("Hello", info["message"])
        print("test_message_content PASSED")

if __name__ == '__main__':
    print("\n" + "="*50)
    print("RUNNING HELLO WORLD TESTS")
    print("="*50 + "\n")
    unittest.main(verbosity=2)
