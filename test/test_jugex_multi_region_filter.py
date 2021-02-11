import unittest
import brainscapes as bs

class TestJugexMultiRegionFilter(unittest.TestCase):

    def test_region_filter(self):
        bs.logger.setLevel("INFO")
        atlas = bs.atlases.MULTILEVEL_HUMAN_ATLAS
        atlas.select_parcellation(bs.parcellations.JULICH_BRAIN_PROBABILISTIC_CYTOARCHITECTONIC_MAPS_V2_5)
        atlas.enable_continuous_map_thresholding(0.2)
        jugex = bs.analysis.DifferentialGeneExpression(atlas)

        input_dict = {
            (1.1111, 2.222, 3.333, "region-name"): {},
            (1.2345, 2.345, 3.000, "region-name"): {},
            (1.1111, 2.222, 3.333, "another region-name"): {}
        }

        expected_dict = {
            (1.1111, 2.222, 3.333, "region-name"): {},
            (1.2345, 2.345, 3.000, "region-name"): {}
        }

        self.assertEqual(jugex._filter_samples(input_dict), expected_dict)


if __name__ == "__main__":
    unittest.main()
