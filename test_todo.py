import unittest
from todo import show_tasks, add_task, remove_task, count_tasks

class TestTodoFunctions(unittest.TestCase):
    
    def test_add_task(self):
        """Test adding a task"""
        tasks = []
        result = add_task(tasks, "Buy groceries")
        self.assertEqual(len(tasks), 1)
        self.assertIn("Buy groceries", tasks)
        self.assertIn("added successfully", result)
        print("✓ test_add_task PASSED")
    
    def test_add_multiple_tasks(self):
        """Test adding multiple tasks"""
        tasks = []
        add_task(tasks, "Task 1")
        add_task(tasks, "Task 2")
        add_task(tasks, "Task 3")
        self.assertEqual(len(tasks), 3)
        print("✓ test_add_multiple_tasks PASSED")
    vagrant halt
    def test_remove_task(self):
        """Test removing a task"""
        tasks = ["Task 1", "Task 2", "Task 3"]
        result = remove_task(tasks, 2)
        self.assertEqual(len(tasks), 2)
        self.assertNotIn("Task 2", tasks)
        self.assertIn("Removed task", result)
        print("✓ test_remove_task PASSED")
    
    def test_remove_invalid_task(self):
        """Test removing with invalid number"""
        tasks = ["Task 1"]
        result = remove_task(tasks, 5)
        self.assertEqual(len(tasks), 1)
        self.assertIn("Invalid", result)
        print("✓ test_remove_invalid_task PASSED")
    
    def test_show_empty_tasks(self):
        tasks = []
        result = show_tasks(tasks)
        self.assertEqual(result, [])
        print("✓ test_show_empty_tasks PASSED")
    
    def test_show_tasks_with_items(self):
        tasks = ["Buy milk", "Study Python", "Exercise"]
        result = show_tasks(tasks)
        self.assertEqual(len(result), 3)
        self.assertIn("Buy milk", result)
        print("✓ test_show_tasks_with_items PASSED")
    
    def test_count_tasks(self):
        tasks = ["Task 1", "Task 2"]
        count = count_tasks(tasks)
        self.assertEqual(count, 2)
        print("✓ test_count_tasks PASSED")

if __name__ == '__main__':
    print("\n" + "="*50)
    print("RUNNING TODO.PY UNIT TESTS")
    print("="*50 + "\n")
    unittest.main(verbosity=2)
