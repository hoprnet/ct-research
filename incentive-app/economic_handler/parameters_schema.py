schema = {
    "type": "object",
    "properties": {
        "parameters": {
            "type": "object",
            "patternProperties": {
                ".*": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number", "minimum": 0},
                        "comment": {"type": "string"},
                    },
                    "required": ["value"],
                }
            },
        },
        "equations": {
            "type": "object",
            "patternProperties": {
                ".*": {
                    "type": "object",
                    "properties": {
                        "formula": {"type": "string"},
                        "condition": {"type": "string"},
                    },
                    "required": ["formula", "condition"],
                }
            },
        },
        "budget_param": {
            "type": "object",
            "properties": {
                "budget": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number", "minimum": 0},
                        "comment": {"type": "string"},
                    },
                    "required": ["value"],
                },
                "budget_period": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number", "minimum": 10},
                        "comment": {"type": "string"},
                    },
                    "required": ["value"],
                },
                "s": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number", "minimum": 0, "maximum": 1},
                        "comment": {"type": "string"},
                    },
                    "required": ["value"],
                },
                "dist_freq": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number", "minimum": 1},
                        "comment": {"type": "string"},
                    },
                    "required": ["value"],
                },
            },
            "required": ["budget", "budget_period", "s", "dist_freq"],
        },
    },
    "required": ["parameters", "equations", "budget_param"],
}
