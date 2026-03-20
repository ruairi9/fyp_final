import unittest
from pipeline_5_code import greet, calculate_sum

class TestPipeline5(unittest.TestCase):
    
    def test_greet(self):
        """Test greeting function"""
        result = greet("Alice")
        self.assertIn("Alice", result)
        self.assertIn("Pipeline #5", result)
        print("✓ test_greet PASSED")
    
    def test_calculate_sum(self):
        """Test sum calculation"""
        result = calculate_sum([1, 2, 3, 4, 5])
        self.assertEqual(result, 15)
        print("✓ test_calculate_sum PASSED")
    
    def test_empty_sum(self):
        """Test sum with empty list"""
        result = calculate_sum([])
        self.assertEqual(result, 0)
        print("✓ test_empty_sum PASSED")

if __name__ == '__main__':
    print("\n" + "="*50)
    print("RUNNING PIPELINE #5 TESTS")
    print("="*50 + "\n")
    unittest.main(verbosity=2)
