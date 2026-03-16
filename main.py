#!/usr/bin/env python3
import sys
from src.cli import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Process interrupted by user.")
        sys.exit(1)
