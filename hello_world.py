def greet():
    """Simple greeting function"""
    return "Hello, World!"

def display_info():
    """Display system information"""
    import platform
    import datetime
    
    info = {
        "message": greet(),
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return info

def main():
    print("=" * 50)
    print("HELLO WORLD APPLICATION")
    print("=" * 50)
    
    info = display_info()
    
    print(f"\n{info['message']}")
    print(f"\nRunning on: {info['platform']}")
    print(f"Python version: {info['python_version']}")
    print(f"Timestamp: {info['timestamp']}")
    
    print("\n✓ Hello World executed successfully!")
    print("=" * 50)

if __name__ == "__main__":
    main()
