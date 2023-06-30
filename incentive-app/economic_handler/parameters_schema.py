schema = {
    "type": "object",
    "properties": {
        "parameters": {
            "type": "object",
            "patternProperties": {
                ".*": {
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "number",
                            "minimum": 0
                        },
                        "comment": {
                            "type": "string"
                        }
                    },
                    "required": ["value"]
                }
            }
        },
        "equations": {
            "type": "object",
            "patternProperties": {
                ".*": {
                    "type": "object",
                    "properties": {
                        "formula": {"type": "string"},
                        "condition": {"type": "string"}
                    },
                    "required": ["formula", "condition"]
                }
            }
        },
         "budget": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "number",
                    "minimum": 0
                },
                "comment": {
                    "type": "string"
                }
            },
            "required": ["value"]
        }
    },
    "required": ["parameters", "equations", "budget"]
}