# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from os import getenv
from pathlib import Path
from types import TracebackType
from typing import IO

import requests
import requests.adapters
from urllib3.util.retry import Retry

default_resource_dir = Path.home() / ".cache" / "halfpipe"
resource_dir = Path(getenv("HALFPIPE_RESOURCE_DIR", str(default_resource_dir)))
resource_dir.mkdir(exist_ok=True, parents=True)

online_resources: dict[str, str | tuple[str, str]] = {
    "index.html": "https://github.com/HALFpipe/QualityCheck/releases/download/0.4.1/index.html",
    "tpl_MNI152NLin6Asym_from_MNI152NLin2009cAsym_mode_image_xfm.h5": "https://figshare.com/ndownloader/files/5534327",
    "tpl_MNI152NLin2009cAsym_from_MNI152NLin6Asym_mode_image_xfm.h5": "https://figshare.com/ndownloader/files/5534330",
    "tpl-MNI152NLin2009cAsym_RegistrationCheckOverlay.nii.gz": "https://figshare.com/ndownloader/files/22447958",
}


@dataclass
class Session(AbstractContextManager):
    session: requests.Session = field(default_factory=requests.session)

    def __post_init__(self):
        max_retries = Retry(
            total=8,
            backoff_factor=10,
            status_forcelist=tuple(range(400, 600)),
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=max_retries)
        for protocol in ["http", "https"]:
            self.session.mount(f"{protocol}://", adapter)

    def __enter__(self) -> requests.Session:
        return self.session

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.session.close()


def urllib_download(url: str, target: str):
    from urllib.request import urlretrieve

    from tqdm import tqdm

    class TqdmUpTo(tqdm):
        def update_to(self, b: int, bsize: int, tsize: int):
            self.total = tsize
            self.update(b * bsize - self.n)  # also sets self.n = b * bsize

    with TqdmUpTo(
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        miniters=1,
        desc=url.split("/")[-1],
    ) as t:
        urlretrieve(url, filename=target, reporthook=t.update_to)


def download(url: str, target: str | Path | None = None) -> str | None:
    import io

    from tqdm import tqdm

    if not url.startswith("http"):
        if not isinstance(target, (str, Path)):
            raise ValueError(f'Expected a string or Path, received "{target}"')
        return urllib_download(url, str(target))

    if target is not None:
        file_handle: IO = open(target, "wb")
    else:
        file_handle = io.BytesIO()

    print(f"Downloading {url}")

    with Session() as session, session.get(url, stream=True) as response:
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        block_size = 1024

        t = tqdm(total=total_size, unit="B", unit_scale=True)

        for block in response.iter_content(block_size):
            if block:  # Filter out keep-alive new chunks
                t.update(len(block))
                file_handle.write(block)

    return_value = None
    if isinstance(file_handle, io.BytesIO):
        return_value = file_handle.getvalue().decode()

    t.close()
    file_handle.close()

    return return_value


def get(file_name: str | Path) -> str:
    if file_name not in online_resources:
        raise ValueError(f"Resource {file_name} not found")

    file_path = resource_dir / file_name
    if file_path.exists():
        return str(file_path)

    resource = online_resources[str(file_name)]

    if isinstance(resource, tuple):
        import json

        jsonstr = download(resource[0])
        if not isinstance(jsonstr, str):
            raise ValueError(f"Expected a string, received {jsonstr}")

        accval = json.loads(jsonstr)
        for key in resource[1:]:
            accval = accval[key]
        resource = accval

    if not isinstance(resource, str):
        raise ValueError(f"Expected a string, received {resource}")

    download(resource, target=file_path)

    return str(file_path)


if __name__ == "__main__":
    from templateflow.api import get as get_template

    get_template("OASIS30ANTs")

    spaces = ["MNI152NLin6Asym", "MNI152NLin2009cAsym"]
    for space in spaces:
        paths = get_template(space, atlas=None, resolution=(1, 2))
        if not isinstance(paths, list) or len(paths) == 0:
            raise ValueError(f"Could not find paths for space {space}: templateflow.api.get returned {paths}")

    for file_name in online_resources.keys():
        get(file_name)
