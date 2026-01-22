FUNC_LABELS = [
    "Unknown",
    "Trigger",
    "Counter",
    "Adder",
    "Comparator",
    "FSM",
    "Decoder",
]

ACTIONS = ["CUT_TIE", "BYPASS", "ISOLATE"]

DEFAULT_HIDDEN = 128
DEFAULT_LAYERS = 3
DEFAULT_ALPHA = 0.5
DEFAULT_EPOCHS = 50
DEFAULT_BATCH = 1
DEFAULT_FUNC_CLASSES = len(FUNC_LABELS)
