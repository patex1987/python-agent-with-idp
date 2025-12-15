# Checks if the package is installed correctly and prints out the path
python -c "import llm_agent, sys; print(llm_agent.__file__); print(sys.path[0])"
python -c "import importlib.metadata as m; print(m.version(\"llm-agent\"))"
