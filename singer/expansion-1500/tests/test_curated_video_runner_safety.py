"""Release-safety checks for the one-shot, research-only video diagnostic workflow."""
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WORKFLOW = REPO / ".github/workflows/curated-video-frame-diagnostic.yml"


class CuratedVideoRunnerSafetyTests(unittest.TestCase):
    def test_only_curated_existing_lead_is_sampled(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("--person-id t1500_0094", source)
        self.assertIn("--download", source)
        self.assertIn("curated_video_frames.py", source)
        self.assertIn("timeout-minutes: 12", source)
        self.assertIn("contents: read", source)
        self.assertIn("retention-days: 3", source)

    def test_no_release_or_source_video_artifact(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        artifact = source.split("uses: actions/upload-artifact@v4", 1)[1]
        self.assertIn("manifest.json", artifact)
        self.assertIn("contact-sheet.jpg", artifact)
        self.assertIn("frame-*.jpg", artifact)
        self.assertNotIn("source.webm", artifact)
        for forbidden in ("git push", "gh pr merge", "actions/deploy-pages",
                          "singer/photos/", "creators.json"):
            self.assertNotIn(forbidden, source)

    def test_not_scheduled_or_triggered_by_unrelated_pipeline_changes(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", source)
        self.assertIn("branches:\n      - automation/celebrity-photo-pipeline", source)
        self.assertIn("- .github/workflows/curated-video-frame-diagnostic.yml", source)
        self.assertNotIn("schedule:", source)


if __name__ == "__main__":
    unittest.main()
