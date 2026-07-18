import preprocess

messy = (
    "Apple Inc.  reported Q4 2024 revenue...\n"
    "\n"
    "-----------------------------\n"
    "\n"
    "    Services revenue reached an all-time high.\n"
    "\n"
    "\n"
    "\n"
    "    \n"
    "iPhone revenue was $46.2B.\n"
)

clean, stats = preprocess.compress(messy, "premium")

print("=== BEFORE ===")
print(repr(messy))
print("\n=== AFTER ===")
print(repr(clean))
print("\n=== STATS ===")
print(stats)
