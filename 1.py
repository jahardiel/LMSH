import sys
from estimador_incertidumbre import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("--demo")
    main()
