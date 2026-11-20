
EMPLOYEE_SCHEMA = {
    "employee_id": {
        "type": "integer",
        "required": True,
        "positive": True,
    },
    "name": {
        "type": "string",
        "required": True,
    },
    "age": {
        "type": "integer",
        "required": True,
        "positive": True,
    },
    "salary": {
        "type": "decimal",
        "required": True,
        "positive": True,
    },
    "email": {
        "type": "email",
        "required": True,
    },
}
