import webbrowser
from threading import Timer

import uvicorn

from workalmanac.app import WorkAlmanac
from workalmanac.viewer.app import create_viewer_app


def serve_viewer(
    app: WorkAlmanac,
    *,
    port: int = 3928,
    open_browser: bool = True,
) -> None:
    url = f"http://127.0.0.1:{port}"
    if open_browser:
        opener = Timer(0.7, webbrowser.open, args=(url,))
        opener.daemon = True
        opener.start()
    print(f"Work Almanac viewer: {url}")
    uvicorn.run(
        create_viewer_app(app),
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
