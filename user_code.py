def main():
    print("Choose an option:")
    print("1 - Hello, World!")
    print("2 - Goodbye, World!")
    choice = input("Enter 1 or 2: ").strip()
    if choice == "1":
        print("Hello, World!")
    elif choice == "2":
        print("Goodbye, World!")
    else:
        print("Invalid choice. Please run the program again.")

if __name__ == "__main__":
    main()
