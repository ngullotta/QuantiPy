from pathlib import Path

if __name__ == "__main__":
    # Results output
    for _file in Path(".").glob("*_results.json"):
        _file.unlink()

    # Graphs
    for _file in Path(".").glob("*.html"):
        _file.unlink()

    # Audit logs
    for _file in Path(".").glob("*_audit.json"):
        _file.unlink
