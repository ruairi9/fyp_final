def greet(name):
    """Simple greeting function"""
    return f"Hello, {name}! Welcome to Pipeline #5"

def calculate_sum(numbers):
    """Calculate sum of numbers"""
    return sum(numbers)

def main():
    print("Pipeline #5 - Test Application")
    print(greet("Developer"))
    
    numbers = [1, 2, 3, 4, 5]
    total = calculate_sum(numbers)
    print(f"Sum of {numbers} = {total}")
    
    print("Pipeline #5 executed successfully!")

if __name__ == "__main__":
    main()
