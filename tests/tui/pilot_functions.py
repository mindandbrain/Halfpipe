# -*- coding: utf-8 -*-
from pathlib import Path


async def _set_work_dir(pilot, work_dir_path, load_from_spec_file=False) -> None:
    await pilot.press("w")
    # click on Browse
    await pilot.click(offset=(60, 15))
    # click to the prompt
    await pilot.click(offset=(74, 38))
    for letter in work_dir_path:
        await pilot.press(letter)
    # close the suggestion box (to see the Enter button
    await pilot.press("esc")
    # click on the Enter button
    await pilot.click(offset=(109, 41))
    if not load_from_spec_file:
        # non existing path modal, click on "Ok"
        await pilot.click(offset=(117, 31))
        # Create new dir modal, click on "Ok"
        await pilot.click(offset=(100, 31))
    else:
        # Spec file found modal, click Load
        await pilot.click(offset=(100, 31))


async def _load_data(pilot, data_path) -> None:
    # switch to input data tab
    await pilot.press("i")
    # click on Browse button
    await pilot.click(offset=(60, 20))
    # click to the prompt
    await pilot.click(offset=(80, 38))
    # type in the path
    for letter in data_path:
        await pilot.press(letter)
    # close the suggestion box (to see the Enter button
    await pilot.press("esc")
    # click on the Enter button
    await pilot.click(offset=(110, 41))
    # click Ok on Modal informing us that the data input is success
    await pilot.click(offset=(121, 31))


async def add_new_feature(pilot, feature_type=None, label=None) -> None:
    feature_type = feature_type if feature_type is not None else "task_based"
    label = label if label is not None else "task_based_1"

    feature_type_yposition = {
        "task_based": 19,
        "seed_based": 21,
        "dual_reg": 23,
        "atlas": 25,
        "reho": 27,
        "falff": 29,
        "preproc": 31,
    }
    # select feature tab
    await pilot.press("f")
    # click on New button
    await pilot.click(offset=(10, 8))
    # click on Task based
    await pilot.click(offset=(100, feature_type_yposition[feature_type]))
    # click in the prompt
    await pilot.click(offset=(94, 25))
    for letter in label:
        await pilot.press(letter)
    # click on Ok button
    await pilot.click(offset=(100, 30))


async def select_images(pilot) -> None:
    # select all images
    await pilot.click(offset=(72, 9))
    await pilot.click(offset=(71, 10))
    await pilot.click(offset=(71, 11))
    await pilot.pause()


async def deselect_conditions(pilot, offset_y=0) -> None:
    # deselect one of the conditions
    await pilot.click(offset=(71, 18 + offset_y))


async def add_contrast_value_column(pilot, label=None, offset_y=0) -> None:
    label = "con1" if label is None else label
    # # click on Add contrast values
    await pilot.click(offset=(108, 38 + offset_y))
    # click in the prompt, for some reasons sometimes needs to be clicked twice
    await pilot.click(offset=(99, 16))
    await pilot.click(offset=(99, 16))
    for letter in label:
        await pilot.press(letter)
    await pilot.press("tab")
    await pilot.press("1")
    await pilot.press("tab")
    await pilot.press("2")
    await pilot.press("tab")
    await pilot.press("3")
    await pilot.press("tab")
    await pilot.press("4")
    await pilot.press("tab")
    await pilot.press("5")
    await pilot.press("tab")
    await pilot.press("6")
    await pilot.press("tab")
    await pilot.press("enter")


async def delete_column(pilot) -> None:
    await pilot.click(offset=(136, 38))


async def scroll_screen_down(pilot) -> None:
    # scroll screen
    await pilot.click(offset=(202, 50))


async def preprocessing_options(pilot) -> None:
    # set smoothing
    await pilot.click(offset=(130, 22))
    await pilot.press("backspace")
    await pilot.press("9")

    # grand mean scaling
    await pilot.click(offset=(134, 25))
    for _i in range(7):
        await pilot.press("backspace")
    for i in "12345":
        await pilot.press(i)

    # switch to frequency based
    await pilot.click(offset=(150, 28))
    # After updating to textual version 0.85.2 a strange thing happens, when clicked on the select menu arrow, the options
    # are unrolled but the whole page is shifted by the number of options (in this case by two presses of up key)
    # Now we need to shift the screen back down (press pagedown).
    # await pilot.click(offset=(138, 32))
    await pilot.click(offset=(138, 34))
    await pilot.click(offset=(50, 10))
    await pilot.press("down")
    await pilot.press("down")
    await pilot.press("down")

    # low
    await pilot.click(offset=(131, 31))
    for _i in range(5):
        await pilot.press("backspace")
    await pilot.press("8")
    # high
    await pilot.press("tab")
    await pilot.press("tab")
    for _i in range(5):
        await pilot.press("backspace")
    await pilot.press("9")


async def remove_confounds(pilot) -> None:
    # make few 'Remove confounds" options
    await pilot.click(offset=(71, 39))
    await pilot.click(offset=(71, 42))
    await pilot.click(offset=(71, 46))


async def check_and_run_tab_refresh(pilot) -> None:
    await pilot.press("r")
    # refresh
    await pilot.click(offset=(83, 9))
    # save
    await pilot.click(offset=(100, 9))
    # press 'Ok' to dismiss the modal
    await pilot.click(offset=(117, 31))


async def scroll_screen_down_spec(pilot) -> None:
    # scroll screen (different layout than in features)
    await pilot.click(offset=(200, 49))


async def toggle_bids_non_bids(pilot) -> None:
    # toggle bids to non bids
    await pilot.click(offset=(113, 14))


async def fill_path_pattern_modal(pilot, path_patter):
    # clear all
    await pilot.click(offset=(120, 30))
    # click to prompt
    await pilot.click(offset=(60, 22))
    for i in path_patter:
        await pilot.press(i)
    # click Ok
    await pilot.click(offset=(125, 40))


async def set_non_bids_data(pilot, t1_pattern_path=None, bold_pattern_path=None, set_repetition_time=False) -> None:
    await pilot.press("i")

    # toggle bids to non bids

    await pilot.click(offset=(113, 14))

    # add T1
    await pilot.click(offset=(57, 35))
    # clear all
    await pilot.click(offset=(120, 30))
    # click to prompt
    await pilot.click(offset=(60, 22))
    # t1_pattern_path = '/tmp/tui_test/ds002785/sub-{subject}/anat/sub-{subject}_T1w.nii.gz'
    for i in t1_pattern_path:
        await pilot.press(i)
    await pilot.click(offset=(125, 40))

    # add bold
    await pilot.click(offset=(57, 46))
    # clear all
    await pilot.click(offset=(120, 30))
    # click to prompt
    await pilot.click(offset=(60, 22))

    # bold_pattern_path = '/tmp/tui_test/ds002785/sub-{subject}/func/sub-{subject}_task-{task}_bold.nii.gz'
    for i in bold_pattern_path:
        await pilot.press(i)
    # clear ok
    await pilot.click(offset=(125, 40))

    if set_repetition_time is True:
        # click No on 'Proceed with these values modal' (Repetition time values)
        await pilot.click(offset=(116, 31))
        # Specify repetition time in seconds: Click into prompt
        await pilot.click(offset=(96, 27))
        # Set time to '9'
        await pilot.press("9")
        # Click Ok to dismiss
        await pilot.click(offset=(96, 31))
    else:
        # click Ok
        await pilot.click(offset=(100, 31))

    # focus on the scroll bar
    await pilot.click(offset=(100, 31))
    for _i in range(15):
        await pilot.press("down")
    # click confirm
    await pilot.click(offset=(100, 47))
    # click Ok on Modal informing us that the data input is success
    await pilot.click(offset=(121, 31))


async def settable_scroll_screen_down(pilot, how_much=20) -> None:
    # scroll screen (different layout than in features)
    for _i in range(how_much):
        await pilot.press("down")


async def run_before_for_reho_falff_preproc(
    pilot, data_path=None, work_dir_path=None, stage=None, file_pattern=None, feature_type=None
) -> None:
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
    async def add_feature():
        await add_new_feature(pilot, feature_type=feature_type, label=feature_type + "_1")
        # deselect second image
        await pilot.click(offset=(71, 10))

        # click in the Smoothing input box, delete the '0' and type '666'
        await pilot.click(offset=(137, 17))

        await pilot.press("backspace")
        for i in "666":
            await pilot.press(i)

        # click in the Grand mean scaling input box, delete the '0' and type '666'
        await pilot.click(offset=(137, 21))
        for _i in range(7):
            await pilot.press("backspace")
        for i in "12345":
            await pilot.press(i)

        # click on the selection arrow of the temporal filter and select 'frequency_based'
        await pilot.click(offset=(151, 23))
        await pilot.click(offset=(151, 27))

        # change low pass filter value to 0.019
        await pilot.click(offset=(137, 26))
        await pilot.press("9")

        # change high pass filter value to 0.19
        await pilot.click(offset=(137, 29))
        await pilot.press("9")

        # remove confounds (activate all)
        await pilot.click(offset=(72, 34))
        await pilot.click(offset=(72, 35))
        await pilot.click(offset=(72, 36))
        await pilot.click(offset=(72, 37))
        await pilot.click(offset=(72, 38))
        await pilot.click(offset=(72, 39))
        await pilot.click(offset=(72, 40))
        await pilot.click(offset=(72, 41))
        await pilot.click(offset=(72, 42))

    async def final_stage_tasks():
        await check_and_run_tab_refresh(pilot)
        await settable_scroll_screen_down(pilot, how_much_down)
        # os.rename(Path(work_dir_path) / "spec.json", Path(work_dir_path) / f"spec_{stage}.json")

    # Map stages to the tasks they should trigger
    tasks_by_stage = {
        "at_features_tab": [add_feature],
        "at_spec_preview": [add_feature, final_stage_tasks],
    }

    # Execute tasks based on the specified stage
    # set work dir
    await _set_work_dir(pilot, work_dir_path)
    # set data dir
    await _load_data(pilot, data_path)
    for task in tasks_by_stage[stage]:
        await task()


async def add_atlas_or_seed_or_map_file_pattern(pilot, file_pattern, event_file_pattern=False):
    # click on "Add" (atlas or seed image or map)
    await pilot.click(offset=(76, 17))

    # select event file type if it is an event file pattern
    if event_file_pattern is True:
        await select_event_file_type(pilot)

    # add atlas file pattern
    await fill_path_pattern_modal(pilot, file_pattern)

    # make choices of the space if it is not an event file pattern
    if event_file_pattern is False:
        await confirm_space_meta_data_after_selecting_file_pattern(pilot)


async def select_event_file_type(pilot):
    # Select event file type from the modal (tsv)
    await pilot.click(offset=(86, 27))
    # Confirm modal by clicking OK
    await pilot.click(offset=(96, 31))


async def confirm_space_meta_data_after_selecting_file_pattern(pilot):
    # click No: Missing Space values modal (Found some values, proceed with those?: No because we want to test the
    # space selection modal (MNI ICBM 2009c vs. MNI ICB 152)).
    await pilot.click(offset=(116, 31))

    # First item should be automatically selected, so we can click directly on "Ok"
    # await pilot.click(offset=(65, 26)) # this is first item in the selection, not used because of the reasons above
    # Click Ok
    await pilot.click(offset=(131, 30))
