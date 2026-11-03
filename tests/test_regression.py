from agenteval.regression import ComparisonRun, RegressionPolicy, compare, demo_gate


def run(passed=True, **changes):
    return ComparisonRun(
        **{
            **dict(
                dataset_id="1",
                expected_cases=1,
                status="COMPLETED",
                judge_provider="fake",
                judge_model="v1",
                rubric_version="v1",
                simulated=True,
                results=[
                    dict(
                        test_case_id="a",
                        passed=passed,
                        correctness=2 if passed else 0,
                        latency_ms=10,
                    )
                ],
            ),
            **changes,
        }
    )


def test_pass_and_fail_regression():
    assert compare(run(), run())["outcome"] == "PASS"
    assert compare(run(), run(False))["outcome"] == "FAIL"


def test_incomplete_and_incompatible_are_inconclusive():
    assert compare(run(), run(status="FAILED"))["outcome"] == "INCONCLUSIVE"
    assert compare(run(), run(dataset_id="other"))["outcome"] == "INCONCLUSIVE"
    assert compare(run(), run(judge_model="other"))["outcome"] == "INCONCLUSIVE"
    assert compare(run(), run(results=[]))["outcome"] == "INCONCLUSIVE"


def test_missing_usage_does_not_pass_token_gate():
    assert compare(run(), run(), RegressionPolicy(max_token_ratio=2))["outcome"] == "INCONCLUSIVE"


async def test_demo_gate_runs_the_real_evaluation_service():
    result = await demo_gate()
    assert result["outcome"] == "PASS" and result["paired_cases"] == 3 and result["simulated"]
