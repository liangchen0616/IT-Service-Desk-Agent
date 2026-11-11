"""Initialize container data without replacing user files, then start one API worker."""
import os
from pathlib import Path
from scripts.initialize import initialize


def main():
    destination = Path(os.environ.get("AGENT_HOME", "/data")).resolve()
    os.environ["AGENT_HOME"] = str(destination)
    initialize(destination)
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, workers=1)


if __name__ == "__main__":
    main()
