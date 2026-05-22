# ─────────────────────────────────────────────
#  MatchKit — Model Registry
# ─────────────────────────────────────────────

# ── Standard tracker models (used in Standard mode) ──
STANDARD_MODELS = [
    {
        "id":          "opencv",
        "name":        "OpenCV Grid",
        "description": "Fast grid-based optical flow. No download needed. Great for clean footage.",
        "source":      "Built-in",
        "requires":    ["cv2", "numpy", "scipy"],
        "quality_presets": {
            "FAST":     {"qualityLevel": 0.01, "winSize": 15, "maxLevel": 2},
            "BALANCED": {"qualityLevel": 0.03, "winSize": 21, "maxLevel": 3},
            "BEST":     {"qualityLevel": 0.06, "winSize": 27, "maxLevel": 4},
        },
    },
    {
        "id":          "cotracker3",
        "name":        "CoTracker3 (Meta AI)",
        "description": "Tracks points jointly and through occlusions. Best for complex shots.",
        "source":      "Meta AI",
        "requires":    ["torch", "cotracker"],
        "quality_presets": {
            "FAST":     {"qualityLevel": 0.01, "winSize": 15, "maxLevel": 2},
            "BALANCED": {"qualityLevel": 0.03, "winSize": 21, "maxLevel": 3},
            "BEST":     {"qualityLevel": 0.06, "winSize": 27, "maxLevel": 4},
        },
    },
    {
        "id":          "tapnext",
        "name":        "TAPNext (Google DeepMind)",
        "description": "Fast and highly capable. Excellent on dynamic shots.",
        "source":      "Google DeepMind",
        "requires":    ["tapnet", "jax", "tensorflow", "einops"],
        "quality_presets": {
            "FAST":     {"qualityLevel": 0.01, "winSize": 15, "maxLevel": 2},
            "BALANCED": {"qualityLevel": 0.03, "winSize": 21, "maxLevel": 3},
            "BEST":     {"qualityLevel": 0.06, "winSize": 27, "maxLevel": 4},
        },
    },
    # ── Add future standard models below this line ──
]

# ── Hybrid models (used in Hybrid mode) ──
HYBRID_MODELS = [
    {
        "id":          "hybrid_opencv_ct3",
        "name":        "OpenCV + CoTracker3",
        "description": "OpenCV finds the best features, CoTracker3 tracks them with AI.",
        "source":      "MatchKit",
        "requires":    ["cv2", "numpy", "scipy", "torch", "cotracker"],
    },
    {
        "id":          "hybrid_opencv_tapnext",
        "name":        "OpenCV + TAPNext",
        "description": "OpenCV finds the best features, TAPNext tracks them with AI.",
        "source":      "MatchKit",
        "requires":    ["cv2", "numpy", "scipy", "tapnet", "jax", "tensorflow", "einops"],
    },
    {
        "id":          "hybrid_ensemble",
        "name":        "Ensemble (CT3 + TAPNext)",
        "description": "Both models track independently, best tracks from each are kept.",
        "source":      "MatchKit",
        "requires":    ["cv2", "numpy", "scipy", "torch", "cotracker", "tapnet", "jax", "tensorflow", "einops"],
    },
    # ── Add future hybrid combinations below this line ──
    # {
    #     "id":          "hybrid_opencv_tapnext",
    #     "name":        "OpenCV + TAPNext",
    #     "description": "OpenCV finds features, TAPNext tracks them.",
    #     "source":      "MatchKit",
    #     "requires":    ["cv2", "numpy", "scipy", "torch", "tapnet"],
    # },
]


# ─────────────────────────────────────────────
#  Helper functions
# ─────────────────────────────────────────────

def get_standard_model(model_id):
    for m in STANDARD_MODELS:
        if m["id"] == model_id:
            return m
    return STANDARD_MODELS[0]


def get_hybrid_model(model_id):
    for m in HYBRID_MODELS:
        if m["id"] == model_id:
            return m
    return HYBRID_MODELS[0]


def get_standard_enum_items():
    return [(m["id"], m["name"], m["description"]) for m in STANDARD_MODELS]


def get_hybrid_enum_items():
    return [(m["id"], m["name"], m["description"]) for m in HYBRID_MODELS]


def check_dependencies(model_id, is_hybrid=False):
    """
    Check if all required libraries for a model are installed.
    Returns (all_ok: bool, missing: list[str])
    """
    import importlib
    model   = get_hybrid_model(model_id) if is_hybrid else get_standard_model(model_id)
    missing = []
    for lib in model.get("requires", []):
        try:
            importlib.import_module(lib)
        except ImportError:
            missing.append(lib)
    return (len(missing) == 0), missing
