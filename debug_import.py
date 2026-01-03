import importlib, traceback

try:
    importlib.import_module("review.models")
    print("IMPORT OK")
except Exception:
    traceback.print_exc()
