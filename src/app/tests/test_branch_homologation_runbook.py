from scripts.review_mission_branches import BranchReview, recommendation, render_markdown


def test_recommendation_requires_pr_before_homologation():
    assert recommendation(False, "completed:success") == "open-pr-required"
    assert recommendation(True, "completed:success") == "ready-for-homologation"
    assert recommendation(True, "completed:failure") == "fix-ci-before-homologation"


def test_render_markdown_includes_branch_ci_and_recommendation():
    report = render_markdown(
        [
            BranchReview(
                name="missao-92-production-monitoring",
                head_sha="abcdef1234567890",
                has_pr=True,
                pr_url="https://github.example/pr/1",
                ci_state="completed:success",
                recommendation="ready-for-homologation",
            )
        ],
        remote="origin",
        base="main",
    )

    assert "missao-92-production-monitoring" in report
    assert "completed:success" in report
    assert "ready-for-homologation" in report
