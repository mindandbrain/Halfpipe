# -*- coding: utf-8 -*-

from functools import partial
from pathlib import Path

from .pilot_functions import (
    _load_data,
    _set_work_dir,
    add_atlas_or_seed_or_map_file_pattern,
    add_new_feature,
    check_and_run_tab_refresh,
    settable_scroll_screen_down,
)


async def run_before(pilot, data_path=None, work_dir_path=None, stage=None, file_pattern=None) -> None:
    # always reload the app first, there is some strange crossinteraction between tests, nothing else helped except using
    # -n 2 flag for the pytest, i.e., running each test with a separate worker
    how_much_down = 35

    pilot.app.reload_ui()
    if isinstance(data_path, Path):
        data_path = str(data_path)
    if isinstance(work_dir_path, Path):
        work_dir_path = str(work_dir_path)
    if isinstance(file_pattern, Path):
        file_pattern = str(file_pattern)
    print("----------------------------", data_path, work_dir_path)

    # Define functions to execute based on stage requirements
    async def add_seed_based_task():
        await add_new_feature(pilot, feature_type="seed_based", label="seed_based_1")
        # click on "Add" (seed images)
        await add_atlas_or_seed_or_map_file_pattern(pilot, file_pattern)

        # deselect second seed file
        await pilot.click(offset=(71, 28))

        # change minimum coverage from 0.8 to 0.85
        await pilot.click(offset=(131, 35))
        await pilot.press("5")
        # press tab to unfocus the input box
        await pilot.press("tab")

    async def final_stage_tasks():
        # click somewhere outside of the form area
        await pilot.click(offset=(50, 10))
        await check_and_run_tab_refresh(pilot)
        await settable_scroll_screen_down(pilot, how_much_down)
        # os.rename(Path(work_dir_path) / "spec.json", Path(work_dir_path) / f"spec_{stage}.json")

    # Map stages to the tasks they should trigger
    tasks_by_stage = {
        "at_features_tab": [add_seed_based_task],
        "at_spec_preview": [add_seed_based_task, final_stage_tasks],
    }

    # Execute tasks based on the specified stage
    # set work dir
    await _set_work_dir(pilot, work_dir_path)
    # set data dir
    await _load_data(pilot, data_path)
    for task in tasks_by_stage[stage]:
        await task()


def test_seed_based_at_features_tab(
    snap_compare, start_app, work_dir_path: Path, downloaded_data_path: Path, atlases_maps_seed_images_path: Path
) -> None:
    """Add file pattern of the seed image in Seed based connectivity. This triggers a modals about the meta information,
    if all goes Ok then there should be the file pattern of the seed image. Moreover, smoothing, grand mean scalling and
    temporal filters are set to Off."""

    seed_image_file_pattern = atlases_maps_seed_images_path / "{seed}_seed_2009.nii.gz"
    run_before_with_extra_args = partial(
        run_before,
        data_path=downloaded_data_path,
        work_dir_path=work_dir_path,
        file_pattern=seed_image_file_pattern,
        stage="at_features_tab",
    )
    assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)


def test_seed_based_at_spec_preview(
    snap_compare, start_app, work_dir_path: Path, downloaded_data_path: Path, atlases_maps_seed_images_path: Path
) -> None:
    """Same as test_seed_based_at_features_tab but now we check the spec preview if the atlas pattern propagated to the spec
    file."""

    seed_image_file_pattern = atlases_maps_seed_images_path / "{seed}_seed_2009.nii.gz"
    run_before_with_extra_args = partial(
        run_before,
        data_path=downloaded_data_path,
        work_dir_path=work_dir_path,
        file_pattern=seed_image_file_pattern,
        stage="at_spec_preview",
    )
    assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)


#
