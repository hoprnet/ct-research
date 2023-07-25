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
                "s": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number", "minimum": 0, "maximum": 1},
                        "comment": {"type": "string"},
                    },
                    "required": ["value"],
                },
            },
            "required": ["budget", "s"],
        },
    },
    "required": ["parameters", "equations", "budget_param"],
}
