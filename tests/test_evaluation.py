from app.evaluation.runner import run_evaluation


def test_evaluation_suite_passes():
    result = run_evaluation()
    assert result["passed"], result["results"]
