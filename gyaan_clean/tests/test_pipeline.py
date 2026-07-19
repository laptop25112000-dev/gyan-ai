import unittest

from gyaan.pipeline import GyaanPipeline


class PipelineTest(unittest.TestCase):
    def test_pipeline_returns_abcdefg_mixed_answer(self):
        run = GyaanPipeline().ask("Explain binary search")
        self.assertEqual(run.final.mixer_model, "abcdefg")
        self.assertIn("GYAAAN answer mixed by abcdefg", run.final.answer)


if __name__ == "__main__":
    unittest.main()
