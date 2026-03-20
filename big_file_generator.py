#!/usr/bin/env python3

"""
Big File Generator
Creates a large text file without requiring any user input.
"""

import os
import hashlib
import random
import string
from datetime import datetime

# Configuration
OUTPUT_FILE = "large_output_file.txt"
TARGET_SIZE_MB = 50   # Change this to make file larger
LINES_PER_BLOCK = 1000


def random_string(length=100):
    """Generate a random string of fixed length."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_line(index):
    """Generate one structured line of data."""
    timestamp = datetime.now().isoformat()
    rand_data = random_string(120)
    hash_value = hashlib.sha256(rand_data.encode()).hexdigest()
    return f"{index},{timestamp},{rand_data},{hash_value}\n"


def generate_large_file():
    print("Starting large file generation...")
    print(f"Target size: {TARGET_SIZE_MB} MB")

    target_bytes = TARGET_SIZE_MB * 1024 * 1024
    current_size = 0
    line_count = 0

    with open(OUTPUT_FILE, "w", buffering=1024*1024) as f:
        while current_size < target_bytes:
            for _ in range(LINES_PER_BLOCK):
                line = generate_line(line_count)
                f.write(line)
                line_count += 1
                current_size += len(line.encode())

            print(f"Progress: {current_size / (1024*1024):.2f} MB written...")

    print("\nDone!")
    print(f"File created: {OUTPUT_FILE}")
    print(f"Total size: {os.path.getsize(OUTPUT_FILE) / (1024*1024):.2f} MB")
    print(f"Total lines: {line_count}")


if __name__ == "__main__":
    generate_large_file()

