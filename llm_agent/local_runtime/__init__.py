"""
Local, in-process runtime infrastructure enabling the API and worker to cooperate within a single Python process.

This allows you to run the run orchestration and run execution locally
without spinning up external infrastructure

- It makes the scope explicit
- It avoids polluting the business infrastructure/
- It avoids leaking test code into prod
- It gives you a clean swap point later
"""
