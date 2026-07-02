"""
Rush scenario: override CITY_HP=80, CITY_DAMAGE=10, then run paired eval.
Does NOT modify existing code - patches at module level before import.
"""
import sys, os, json, math

# Patch constants BEFORE any prototype import
import importlib
import prototype.constants as _c
_c.CITY_HP = 80
_c.CITY_DAMAGE = 10
importlib.reload(_c)

# Now import eval_matrix which will import the patched constants
from prototype.eval_matrix import main

# We can't pass args directly, so modify sys.argv
sys.argv = [
    "eval_matrix",
    "--paired",
    "--ais", "greedy,greedy",
    "--games", "500",
    "--size", "15",
    "--gen", "balanced",
    "--output", os.path.join(os.path.dirname(__file__), "rush"),
    "--save-raw",
]

if __name__ == "__main__":
    main()
