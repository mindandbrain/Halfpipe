# -*- coding: utf-8 -*-

from functools import partial
from pathlib import Path

from .pilot_functions import (
    _set_work_dir,
    add_atlas_or_seed_or_map_file_pattern,
    add_new_feature,
    check_and_run_tab_refresh,
    set_non_bids_data,
    settable_scroll_screen_down,
)


async def run_before(
    pilot, data_path=None, work_dir_path=None, stage=None, file_pattern=None, t1_path_pattern=None, bold_path_pattern=None
) -> None:
    # always reload the app first, there is some strange crossinteraction between tests, nothing else helped except using
    # -n 2 flag for the pytest, i.e., running each test with a separate worker
    how_much_down = 0

    pilot.app.reload_ui()
    if isinstance(data_path, Path):
        data_path = str(data_path)
    if isinstance(work_dir_path, Path):
        work_dir_path = str(work_dir_path)
    if isinstance(file_pattern, Path):
        file_pattern = str(file_pattern)

    if isinstance(t1_path_pattern, Path):
        t1_path_pattern = str(t1_path_pattern)
    if isinstance(bold_path_pattern, Path):
        bold_path_pattern = str(bold_path_pattern)

    async def add_feature_related_tasks():
        await add_new_feature(pilot)
        await add_atlas_or_seed_or_map_file_pattern(pilot, file_pattern, event_file_pattern=True)

    async def duplicate():
        await pilot.click(offset=(10, 12))

    async def final_stage_tasks():
        # click somewhere outside of the form area
        await pilot.click(offset=(50, 10))
        await check_and_run_tab_refresh(pilot)
        await settable_scroll_screen_down(pilot, how_much_down)
        # os.rename(Path(work_dir_path) / "spec.json", Path(work_dir_path) / f"spec_{stage}.json")

    # Map stages to the tasks they should trigger
    tasks_by_stage = {
        "at_features_tab": [add_feature_related_tasks],
        "at_features_duplicate": [add_feature_related_tasks, duplicate],
        "at_spec_preview": [add_feature_related_tasks, final_stage_tasks],
        "duplicate_at_spec_preview": [add_feature_related_tasks, duplicate, final_stage_tasks],
    }
    if stage == "at_spec_preview":
        how_much_down = 60
    elif stage == "duplicate_at_spec_preview":
        how_much_down = 36

    # Execute tasks based on the specified stage
    # set work dir
    await _set_work_dir(pilot, work_dir_path)
    # set data dir
    await set_non_bids_data(pilot, t1_path_pattern, bold_path_pattern)
    # same reason for this as at work_tab case
    await pilot.click(offset=(25, 25))
    await pilot.click(offset=(25, 25))

    for task in tasks_by_stage[stage]:
        await task()


def test_task_based_non_bids_at_features_tab(
    snap_compare, start_app, work_dir_path: Path, downloaded_data_path: Path, t1_path_pattern: Path, bold_path_pattern: Path
) -> None:
    """Add file pattern of the event file in Task-based connectivity. This does _not_ trigger a modals about the meta
    information. If all goes Ok then there should be the file pattern of the event file and conditions should be loaded
    """

    file_pattern = "/tmp/tui_test/ds002785/sub-{subject}/func/sub-{subject}_task-{task}_events.tsv"

    run_before_with_extra_args = partial(
        run_before,
        data_path=downloaded_data_path,
        work_dir_path=work_dir_path,
        stage="at_features_tab",
        file_pattern=file_pattern,
        t1_path_pattern=t1_path_pattern,
        bold_path_pattern=bold_path_pattern,
    )
    assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)


def test_task_based_non_bids_at_spec_preview(
    snap_compare, start_app, work_dir_path: Path, downloaded_data_path: Path, t1_path_pattern: Path, bold_path_pattern: Path
) -> None:
    """Same as test_reho_at_features_tab but now we check the spec preview if the atlas pattern propagated to the spec
    file."""

    file_pattern = "/tmp/tui_test/ds002785/sub-{subject}/func/sub-{subject}_task-{task}_events.tsv"

    run_before_with_extra_args = partial(
        run_before,
        data_path=downloaded_data_path,
        work_dir_path=work_dir_path,
        stage="at_spec_preview",
        file_pattern=file_pattern,
        t1_path_pattern=t1_path_pattern,
        bold_path_pattern=bold_path_pattern,
    )
    assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)


def test_task_based_non_bids_at_features_tab_duplicate(
    snap_compare, start_app, work_dir_path: Path, downloaded_data_path: Path, t1_path_pattern: Path, bold_path_pattern: Path
) -> None:
    """Unselect a condition, make a column in the table, delete it, make it again"""
    file_pattern = "/tmp/tui_test/ds002785/sub-{subject}/func/sub-{subject}_task-{task}_events.tsv"

    run_before_with_extra_args = partial(
        run_before,
        data_path=downloaded_data_path,
        work_dir_path=work_dir_path,
        stage="at_features_duplicate",
        file_pattern=file_pattern,
        t1_path_pattern=t1_path_pattern,
        bold_path_pattern=bold_path_pattern,
    )
    assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)


def test_task_based_features_duplicate_at_spec_preview(
    snap_compare, start_app, work_dir_path: Path, downloaded_data_path: Path, t1_path_pattern: Path, bold_path_pattern: Path
) -> None:
    """Unselect a condition, make a column in the table, delete it, make it again"""
    file_pattern = "/tmp/tui_test/ds002785/sub-{subject}/func/sub-{subject}_task-{task}_events.tsv"

    run_before_with_extra_args = partial(
        run_before,
        data_path=downloaded_data_path,
        work_dir_path=work_dir_path,
        stage="duplicate_at_spec_preview",
        file_pattern=file_pattern,
        t1_path_pattern=t1_path_pattern,
        bold_path_pattern=bold_path_pattern,
    )
    assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)


#
# def test_task_based_features_at_spec_preview(
#     snap_compare, start_app, fixed_tmp_path: Path, work_dir_path: Path, downloaded_data_path: Path
# ) -> None:
#     """Continue from p1 and p2 to spec preview (last tab), also the spec file is saved for further inspection"""
#     run_before_with_extra_args = partial(
#         run_before, data_path=downloaded_data_path, work_dir_path=work_dir_path, stage="at_spec_preview"
#     )
#
#     assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)


# def test_task_based_features_at_features_duplicate(
#     snap_compare, start_app, fixed_tmp_path: Path, work_dir_path: Path, downloaded_data_path: Path
# ) -> None:
#     """Continue from p1 and p2, click on duplicate, scroll to the part where the table and preprocessing
#     options can be seen."""
#     run_before_with_extra_args = partial(
#         run_before, data_path=downloaded_data_path, work_dir_path=work_dir_path, stage="at_features_duplicate"
#     )
#
#     assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)
#
#
# def test_task_based_features_duplicate_at_spec_preview(
#     snap_compare, start_app, fixed_tmp_path: Path, work_dir_path: Path, downloaded_data_path: Path
# ) -> None:
#     """Continue from test_task_based_features_at_features_duplicate to spec preview because we need to be sure that the
#     duplicate was propagated also the the cache and further to the spec file."""
#     run_before_with_extra_args = partial(
#         run_before, data_path=downloaded_data_path, work_dir_path=work_dir_path, stage="duplicate_at_spec_preview"
#     )
#
#     assert snap_compare(app=start_app, terminal_size=(204, 53), run_before=run_before_with_extra_args)
