import sys

with open('optimizer/main.py', 'r') as f:
    content = f.read()

search_arg = """    parser.add_argument("--epsilon", type=float, default=5.0, help="Mismatch threshold for surrogate backtests")"""
replace_arg = """    parser.add_argument("--epsilon", type=float, default=5.0, help="Mismatch threshold for surrogate backtests")
    parser.add_argument("--use-ml-optimizer", action="store_true", help="Use Optuna-based ML optimizer instead of LLM.")"""

if search_arg not in content:
    print("Error finding arg block")
    sys.exit(1)

content = content.replace(search_arg, replace_arg)

with open('optimizer/main.py', 'w') as f:
    f.write(content)
