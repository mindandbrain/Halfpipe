# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from os import getenv
from pathlib import Path
from typing import IO

default_resource_dir = Path.home() / ".cache" / "halfpipe"
resource_dir = Path(getenv("HALFPIPE_RESOURCE_DIR", str(default_resource_dir)))
resource_dir.mkdir(exist_ok=True, parents=True)

online_resources: dict[str, str] = {
    "index.html": "https://github.com/HALFpipe/QualityCheck/releases/download/0.4.1/index.html",
    "tpl_MNI152NLin6Asym_from_MNI152NLin2009cAsym_mode_image_xfm.h5": "https://figshare.com/ndownloader/files/5534327",
    "tpl_MNI152NLin2009cAsym_from_MNI152NLin6Asym_mode_image_xfm.h5": "https://figshare.com/ndownloader/files/5534330",
    "tpl-MNI152NLin2009cAsym_RegistrationCheckOverlay.nii.gz": "https://figshare.com/ndownloader/files/22447958",
}


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

    import requests
    from tqdm import tqdm

    if not url.startswith("http"):
        assert isinstance(target, (str, Path))
        return urllib_download(url, str(target))

    if target is not None:
        file_handle: IO = open(target, "wb")
    else:
        file_handle = io.BytesIO()

    print(f"Downloading {url}")

    with requests.get(url, stream=True) as response:
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))  # type: ignore
        block_size = 1024

        t = tqdm(total=total_size, unit="B", unit_scale=True)

        for block in response.iter_content(block_size):  # type: ignore
            if block:  # filter out keep-alive new chunks
                t.update(len(block))
                file_handle.write(block)

    res = None
    if isinstance(file_handle, io.BytesIO):
        res = file_handle.getvalue().decode()

    t.close()
    file_handle.close()

    return res


def get(file_name: str | Path) -> str:
    assert file_name in online_resources, f"Resource {file_name} not found"

    file_path = resource_dir / file_name
    if file_path.exists():
        return str(file_path)

    resource = online_resources[str(file_name)]

    if isinstance(resource, tuple):
        import json

        jsonstr = download(resource[0])
        assert isinstance(jsonstr, str)

        accval = json.loads(jsonstr)
        for key in resource[1:]:
            accval = accval[key]
        resource = accval

    download(resource, target=file_path)

    return str(file_path)


if __name__ == "__main__":
    from templateflow import api as tfapi

    tfapi.get("OASIS30ANTs")

    spaces = ["MNI152NLin6Asym", "MNI152NLin2009cAsym", "MNIPediatricAsym"]
    for space in spaces:
        paths = tfapi.get(space, atlas=None, resolution=(1, 2))
        assert isinstance(paths, list)
        assert len(paths) > 0

    for file_name in online_resources.keys():
        get(file_name)
