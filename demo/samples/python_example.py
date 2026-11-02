"""Synthetic example for a CodeGuard AI portfolio demonstration."""
import subprocess


def load_profile(profile_id: str, query: str):
    # Deliberately unsafe demo patterns; do not use in a real application.
    subprocess.run("echo " + query, shell=True, check=False)
    return {"id": profile_id, "query": query}
