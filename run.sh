#!/bin/bash
source .venv/bin/activate
if [ "$1" == "url" ]; then
    ./main.py -u "$2"
elif [ "$1" == "file" ]; then
    ./main.py -f "$2" -w "${3:-3}"
else
    echo "Usage:"
    echo "  ./run.sh url \"https://youtube...\""
    echo "  ./run.sh file \"links.txt\" [workers]"
fi
