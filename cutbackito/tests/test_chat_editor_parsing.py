"""Pure-data test for EditPlan parsing — no API call."""

from app.chat_editor import EditPlan


def test_edit_plan_from_tool_input():
    payload = {
        "summary": "three best laughs",
        "clips": [
            {
                "title": "punchline",
                "start": 12.0,
                "end": 42.0,
                "camera": "cam_a",
                "format": "vertical_9_16",
                "caption": "",
            },
            {
                "title": "wide reaction",
                "start": 130,
                "end": 160,
                "camera": "auto",
                "format": "landscape_16_9",
            },
        ],
    }
    plan = EditPlan.from_tool_input(payload)
    assert plan.summary.startswith("three")
    assert len(plan.clips) == 2
    assert plan.clips[0].camera == "cam_a"
    assert plan.clips[0].format == "vertical_9_16"
    assert plan.clips[1].caption == ""
