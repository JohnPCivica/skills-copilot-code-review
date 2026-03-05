---
applyTo: "backend/**/*,*.py"
---

## Backend Guidelines

- All API endpoints must be defined in the `routers` folder.
- Load example database content from the `database.py` file.
- Log detailed error information on the server and return only user-friendly, non-sensitive error messages (e.g., validation errors) to the frontend. Do not expose internal implementation details, stack traces, or sensitive data in API responses.
- Ensure all APIs are explained in the documentation.
- Verify changes in the backend are reflected in the frontend (`src/static/**`). If possible breaking changes are found, mention them to the developer.