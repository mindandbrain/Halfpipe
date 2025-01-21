# -*- coding: utf-8 -*-

from functools import partial
from pathlib import Path

from .pilot_functions import (
    _load_data,
    _set_work_dir,
    add_contrast_value_column,
    add_new_feature,
    check_and_run_tab_refresh,
    delete_column,
    deselect_conditions,
    preprocessing_options,
    remove_confounds,
    scroll_screen_down,
    settable_scroll_screen_down,
)


async def run_before(pilot, data_path=None, work_dir_path=None, stage=None) -> None:
    # always reload the app first, there is some strange crossinteraction between tests, nothing else helped except using
    # -n 2 flag for the pytest, i.e., running each test with a separate worker
    how_much_down = 0

    pilot.app.reload_ui()
    if isinstance(data_path, Path):
        data_path = str(data_path)
    if isinstance(work_dir_path, Path):
        work_dir_path = str(work_dir_path)
    print("----------------------------", data_path, work_dir_path)

    # Define functions to execute based on stage requirements
    async def add_feature_related_tasks():
        await add_new_feature(pilot)
        await deselect_conditions(pilot)
        await add_contrast_value_column(pilot, label="col1")
        await delete_column(pilot)
        await add_contrast_value_column(pilot, label="col2")

    async def feature_p2_and_final_tasks():
        await scroll_screen_down(pilot)
        await preprocessing_options(pilot)
        await remove_confounds(pilot)

    async def duplicate():
        await pilot.click(offset=(10, 12))
        await scroll_screen_down(pilot)

    async def final_stage_tasks():
        await check_and_run_tab_refresh(pilot)
        await settable_scroll_screen_down(pilot, how_much_down)
        # os.rename(Path(work_dir_path) / "spec.json", Path(work_dir_path) / f"spec_{stage}.json")

    # Map stages to the tasks they should trigger
    tasks_by_stage = {
        "at_features_tab_p1": [add_feature_related_tasks],
        "at_features_tab_p2": [add_feature_related_tasks, feature_p2_and_final_tasks],
        "at_spec_preview": [add_feature_related_tasks, feature_p2_and_final_tasks, final_stage_tasks],
        "at_features_duplicate": [add_feature_related_tasks, feature_p2_and_final_tasks, duplicate],
        "duplicate_at_spec_preview": [add_feature_related_tasks, feature_p2_and_final_tasks, duplicate, final_stage_tasks],
    }
    if stage == "at_spec_preview":
        how_much_down = 60
    elif stage == "duplicate_at_spec_preview":
        how_much_down = 36

    # Execute tasks based on the specified stage
    # set work dir
    await _set_work_dir(pilot, work_dir_path)
    # set data dir
    await _load_data(pilot, data_path)
    for task in tasks_by_stage[stage]:
        await task()


def test_task_based_at_features_tab_p1(snap_compare, start_app, work_dir_path: Path, downloaded_data_path: Path) -> None:
    """Add Task-based feature, unselect a condition, make a column in the table, delete it, make it again"""
    run_before_with_extra_args = partial(
        run_before, data_path=downloaded_data_path, work_dir_path=work_dir_path, stage="at_features_tab_p1"
    )
    assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)


def test_task_based_at_features_tab_p2(
    snap_compare, start_app, fixed_tmp_path: Path, work_dir_path: Path, downloaded_data_path: Path
) -> None:
    """Continue from test_task_based_at_features_tab_p1, scroll, make choices in the preprocessing part"""
    run_before_with_extra_args = partial(
        run_before, data_path=downloaded_data_path, work_dir_path=work_dir_path, stage="at_features_tab_p2"
    )

    assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)


def test_task_based_features_at_spec_preview(
    snap_compare, start_app, fixed_tmp_path: Path, work_dir_path: Path, downloaded_data_path: Path
) -> None:
    """Continue from test_task_based_at_features_tab_p2 to spec preview (last tab), also the spec file is saved for
    further inspection."""

    run_before_with_extra_args = partial(
        run_before, data_path=downloaded_data_path, work_dir_path=work_dir_path, stage="at_spec_preview"
    )

    assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)


def test_task_based_features_at_features_duplicate(
    snap_compare, start_app, fixed_tmp_path: Path, work_dir_path: Path, downloaded_data_path: Path
) -> None:
    """Continue from test_task_based_at_features_tab_p2, click on duplicate, scroll to the part where the table and
    preprocessing options can be seen."""
    run_before_with_extra_args = partial(
        run_before, data_path=downloaded_data_path, work_dir_path=work_dir_path, stage="at_features_duplicate"
    )

    assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)


def test_task_based_features_duplicate_at_spec_preview(
    snap_compare, start_app, fixed_tmp_path: Path, work_dir_path: Path, downloaded_data_path: Path
) -> None:
    """Continue from test_task_based_features_at_features_duplicate to spec preview because we need to be sure that the
    duplicate was propagated also the the cache and further to the spec file."""

    run_before_with_extra_args = partial(
        run_before, data_path=downloaded_data_path, work_dir_path=work_dir_path, stage="duplicate_at_spec_preview"
    )

    assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)
