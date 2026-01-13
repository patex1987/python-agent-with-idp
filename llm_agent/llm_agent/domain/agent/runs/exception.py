class RunNotFoundError(Exception):
    """ """

    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"Run {run_id} not found")
