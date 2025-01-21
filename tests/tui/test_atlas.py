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


async def run_before(pilot, data_path=None, work_dir_path=None, stage=None, atlas_file_pattern=None) -> None:
    # always reload the app first, there is some strange crossinteraction between tests, nothing else helped except using
    # -n 2 flag for the pytest, i.e., running each test with a separate worker
    how_much_down = 35

    pilot.app.reload_ui()
    if isinstance(data_path, Path):
        data_path = str(data_path)
    if isinstance(work_dir_path, Path):
        work_dir_path = str(work_dir_path)
    if isinstance(atlas_file_pattern, Path):
        atlas_file_pattern = str(atlas_file_pattern)
    print("----------------------------", data_path, work_dir_path)

    # Define functions to execute based on stage requirements
    async def add_atlas_task():
        await add_new_feature(pilot, feature_type="atlas", label="atlas_1")

        # Add atlas file pattern
        await add_atlas_or_seed_or_map_file_pattern(pilot, atlas_file_pattern)

        # change minimum coverage from 0.8 to 0.85
        await pilot.click(offset=(131, 35))
        await pilot.press("5")

        # turn off smoothing
        await pilot.click(offset=(118, 41))
        # turn off grand mean scalling
        await pilot.click(offset=(118, 44))
        # turn off the temporal filter
        await pilot.click(offset=(118, 47))

    async def duplicate():
        await pilot.click(offset=(10, 12))
        # await scroll_screen_down(pilot)

    async def final_stage_tasks():
        # click somewhere outside of the form area
        await pilot.click(offset=(50, 10))
        await check_and_run_tab_refresh(pilot)
        await settable_scroll_screen_down(pilot, how_much_down)
        # os.rename(Path(work_dir_path) / "spec.json", Path(work_dir_path) / f"spec_{stage}.json")

    # Map stages to the tasks they should trigger
    tasks_by_stage = {
        "at_features_tab": [add_atlas_task],
        "at_spec_preview": [add_atlas_task, final_stage_tasks],
        "at_features_duplicate": [add_atlas_task, duplicate],
        "duplicate_at_spec_preview": [add_atlas_task, duplicate, final_stage_tasks],
    }
    # if stage == "at_spec_preview":
    #     how_much_down = 60
    # elif stage == "duplicate_at_spec_preview":
    #     how_much_down = 36

    # Execute tasks based on the specified stage
    # set work dir
    await _set_work_dir(pilot, work_dir_path)
    # set data dir
    await _load_data(pilot, data_path)
    for task in tasks_by_stage[stage]:
        await task()


def test_atlas_at_features_tab(
    snap_compare, start_app, work_dir_path: Path, downloaded_data_path: Path, atlases_maps_seed_images_path: Path
) -> None:
    """Add file pattern of the atlas for the Atlas-based connectivity matrix feature. This triggers a modals about the meta
    information, if all goes Ok then there should be the file pattern of the atlas. Moreover, smoothing, grand mean scalling
    and temporal filters are set to Off."""

    atlas_file_pattern = atlases_maps_seed_images_path / "tpl-MNI152NLin2009cAsym_atlas-{atlas}.nii"
    run_before_with_extra_args = partial(
        run_before,
        data_path=downloaded_data_path,
        work_dir_path=work_dir_path,
        atlas_file_pattern=atlas_file_pattern,
        stage="at_features_tab",
    )
    assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)


def test_atlas_at_spec_preview(
    snap_compare, start_app, work_dir_path: Path, downloaded_data_path: Path, atlases_maps_seed_images_path: Path
) -> None:
    """Same as test_atlas_at_features_tab but now we check the spec preview if the atlas pattern propagated to the spec
    file."""

    atlas_file_pattern = atlases_maps_seed_images_path / "tpl-MNI152NLin2009cAsym_atlas-{atlas}.nii"
    run_before_with_extra_args = partial(
        run_before,
        data_path=downloaded_data_path,
        work_dir_path=work_dir_path,
        atlas_file_pattern=atlas_file_pattern,
        stage="at_spec_preview",
    )
    assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)


def test_atlas_at_features_duplicate(
    snap_compare, start_app, work_dir_path: Path, downloaded_data_path: Path, atlases_maps_seed_images_path: Path
) -> None:
    """Same as test_atlas_at_features_tab but now we duplicate the feature and check if the file pattern is still there and
    if the smoothing, grand mean scalling and temporal filters are still Off."""

    atlas_file_pattern = atlases_maps_seed_images_path / "tpl-MNI152NLin2009cAsym_atlas-{atlas}.nii"
    run_before_with_extra_args = partial(
        run_before,
        data_path=downloaded_data_path,
        work_dir_path=work_dir_path,
        atlas_file_pattern=atlas_file_pattern,
        stage="at_features_duplicate",
    )
    assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)


def test_duplicate_at_spec_preview(
    snap_compare, start_app, work_dir_path: Path, downloaded_data_path: Path, atlases_maps_seed_images_path: Path
) -> None:
    """Same as test_atlas_at_features_duplicate but now we check the spec preview. The features and settings should be
    duplicated but the atlas file pattern should be only one."""

    atlas_file_pattern = atlases_maps_seed_images_path / "tpl-MNI152NLin2009cAsym_atlas-{atlas}.nii"
    run_before_with_extra_args = partial(
        run_before,
        data_path=downloaded_data_path,
        work_dir_path=work_dir_path,
        atlas_file_pattern=atlas_file_pattern,
        stage="duplicate_at_spec_preview",
    )
    assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)
