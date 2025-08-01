import os
import sys
import json
import unittest
import warnings
import numpy as np
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import musictranslator
from musictranslator.drum_analysis_service.app import _init_process_pool_worker
from musictranslator.drum_analysis_service.DrumMLA import DrumMLA

warnings.simplefilter('once', UserWarning)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DRUM_SAMPLES_FILE = os.path.join(PROJECT_ROOT, 'data_backend', 'drum_sample_features.json')

class TestDrumMLA(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Load known drum samples once for all tests in this class.
        """
        if not os.path.exists(DRUM_SAMPLES_FILE):
            raise FileNotFoundError(f"Drum samples file not found: {DRUM_SAMPLES_FILE}")

        with open(DRUM_SAMPLES_FILE, 'r') as f:
            cls.real_known_samples = json.load(f)

        print(f"\nLoaded {len(cls.real_known_samples)} real drum samples for testing.")

        # Print counts per drum category, type, and qualifier to see
        # data distribution
        category_counts = defaultdict(int)
        type_counts = defaultdict(int)
        qualifier_counts = defaultdict(int)

        for sample in cls.real_known_samples:
            category = sample.get('drum_category', 'unknown_category')
            drum_type = sample.get('drum_type', 'unknown_type')
            qualifier = sample.get('qualifier', 'no_qualifier')

            category_counts[category] += 1
            type_counts[f"{category}/{drum_type}"] += 1
            if qualifier != "no_qualifier":
                qualifier_counts[f"{category}/{drum_type}/{qualifier}"] += 1

        print("Distribution of known drum categories:")
        for cat, count in sorted(category_counts.items()):
            print(f"- {cat}: {count}")

        print("\nDistribution of known drum types (within categories):")
        for dt, count in sorted(type_counts.items()):
            print(f"- {dt}: {count}")

        print("\nDistribution of known qualifiers (within types/categories):")
        for qual, count in sorted(qualifier_counts.items()):
            print(f"- {qual}: {count}")

    def setUp(self):
        # Initialize DrumMLA with the real known samples for each test
        self.mla = DrumMLA(known_samples_data=self.real_known_samples)

        # A sample extracted feature set to test classification
        self.sample_extracted_feature = {
            "onset_time": 1.2,
            "duration": 0.21,
            "relative_volume": 0.82,
            "dominant_frequency": 2400.0,
            "spectral_centroid": 2100.0,
            "spectral_rolloff": 4600.0,
            "spectral_flux": 0.52,
            "mfccs": [1.1] * 13
        }

        # Another sample, clearly an "other/unknown"
        self.unknown_extracted_feature = {
            "onset_time": 2.0,
            "duration": 1.0, # Very long duration
            "relative_volume": 0.1,
            "dominant_frequency": 1000.0,
            "spectral_centroid": 1000.0,
            "spectral_rolloff": 2000.0,
            "spectral_flux": 0.05,
            "mfccs": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]
        }

    def test_initialization(self):
        """Test that the DrumMLA can be initialized."""
        mla_empty = DrumMLA()
        self.assertIsNotNone(mla_empty)
        self.assertIsInstance(mla_empty.known_samples, dict)
        self.assertEqual(len(mla_empty.known_samples), 0)

        # Test with loaded samples (self.mla initialized with real_known_samples)
        self.assertGreater(len(self.mla.known_samples), 0)

        # Check that 'mfccs' are stored as numpy arrays (or similar
        # numerical type) and that excluded features are not present
        # in the processed data.
        # Pick one known sample to check internal structure
        # Accessing nested defaultdict: category -> type -> qualifier
        # -> list of samples
        first_category = next(iter(self.mla.known_samples))
        first_type = next(iter(self.mla.known_samples[first_category]))
        first_qualifier = next(iter(self.mla.known_samples[first_category][first_type]))
        first_sample_data = self.mla.known_samples[first_category][first_type][first_qualifier][0]

        self.assertIsInstance(first_sample_data['mfccs'], np.ndarray)
        self.assertEqual(len(first_sample_data['mfccs']), 13)
        self.assertIn('spectral_centroid', first_sample_data)
        self.assertIn('spectral_rolloff', first_sample_data)
        self.assertIn('spectral_flux', first_sample_data)
        self.assertIn('duration', first_sample_data)

        # Ensure excluded features are NOT in the prepared data
        self.assertNotIn('onset_time', first_sample_data)
        self.assertNotIn('relative_volume', first_sample_data)
        self.assertNotIn('dominant_frequency', first_sample_data)

    def test_add_known_samples(self):
        """
        Test adding known samples and their correct processing
        and hierarchical storage.
        """
        mla = DrumMLA()
        initial_samples_count = len(self.real_known_samples)

        # Add half of the samples
        subset_samples = self.real_known_samples[:initial_samples_count // 2]
        mla.add_known_samples(subset_samples)

        # Verify that the known_samples structure is populated
        total_processed_samples = 0
        for cat_dict in mla.known_samples.values():
            for type_dict in cat_dict.values():
                for qual_list in type_dict.values():
                    total_processed_samples += len(qual_list)

        self.assertGreater(len(mla.known_samples), 0)
        self.assertLessEqual(total_processed_samples,
                             initial_samples_count // 2)

        # Add the remaining half
        mla.add_known_samples(self.real_known_samples[initial_samples_count // 2:])

        # Verify total count (count of individual samples that were successfully added)
        final_processed_samples = 0
        for cat_dict in mla.known_samples.values():
            for type_dict in cat_dict.values():
                for qual_list in type_dict.values():
                    final_processed_samples += len(qual_list)

        # It's hard to assert exact equality here due to potential
        # skips from _prepare_features and category/type/qualifier
        # validation. We'll just assert it's significant.
        self.assertGreaterEqual(final_processed_samples,
                                initial_samples_count * 0.9)

    def test_classify_single_drum_event_with_real_data(self):
        """
        Test classification for a single event using real data.
        We'll pick an actual known sample and slightly perturb it.
        """
        # Take a real snare drum sample from the loaded data
        snare_samples = [s for s in self.real_known_samples if s.get("drum_category") == "snare"]
        if not snare_samples:
            self.skipTest("No 'snare_drum' samples in real_known_samples to test.")

        base_snare = snare_samples[0]

        # Create a slighly perturbed version for testing
        test_snare_sample = base_snare.copy()
        test_snare_sample["spectral_centroid"] *= 1.002
        test_snare_sample["spectral_rolloff"] *= 0.999
        test_snare_sample["spectral_flux"] *= 1.003
        test_snare_sample["duration"] *= 1.001
        test_snare_sample["mfccs"] = [mfcc * 1.003 for mfcc in test_snare_sample["mfccs"]]

        prediction = self.mla.classify_drum_event(
            test_snare_sample,
            min_category_confidence=0.80,
            min_type_confidence=0.80,
            min_qualifier_confidence=0.50)

        # Assertions for hierarchical prediction
        self.assertEqual(prediction["drum_category"]["value"],
                         base_snare["drum_category"])
        self.assertGreaterEqual(
            prediction["drum_category"]["confidence"], 0.80)

        # Default value is closed_band
        self.assertEqual(prediction["drum_type"]["value"],
                         base_snare["drum_type"])
        self.assertGreaterEqual(prediction["drum_type"]["confidence"],
                                0.80)

        # Handle qualifier: it can be None in original data, but
        # 'no_qualifier' in prediction
        expected_qualifier = base_snare.get("qualifier")
        if expected_qualifier is None:
            expected_qualifier = "no_qualifier"
        self.assertEqual(prediction["qualifier"]["value"],
                         expected_qualifier)
        # Qualifier confidence might be lower if few samples, but
        # still expect good for direct match
        self.assertGreaterEqual(prediction["qualifier"]["confidence"],
                                0.50)

    def test_classify_all_known_drum_types(self):
        """
        Test that each known drum type (category, type, qualifier
        combo) be correctly classified when presented with itself
        (or a very close variant) from the loaded dataset.
        """
        successful_classifications = defaultdict(int)

        # Create a dictionary to hold one sample for each unique
        # category/type/qualifier combination
        samples_to_test_per_combo = {}
        for sample in self.real_known_samples:
            category = sample.get("drum_category")
            drum_type = sample.get("drum_type")
            qualifier = sample.get("qualifier") if sample.get("qualifier") is not None else "no_qualifier"

            if category and drum_type:
                combo_key = f"{category}/{drum_type}/{qualifier}"
                if combo_key not in samples_to_test_per_combo:
                    samples_to_test_per_combo[combo_key] = sample

        if not samples_to_test_per_combo:
            self.fail("No valid drum category/type combinations found in real_known_samples to test.")

        # Iterate through one sample per combo and test
        # hierarchical classification
        for expected_combo, test_sample in samples_to_test_per_combo.items():
            expected_category, expected_type, expected_qualifier = expected_combo.split('/')

            prediction = self.mla.classify_drum_event(
                test_sample,
                min_category_confidence=0.70,
                min_type_confidence=0.50,
                min_qualifier_confidence=0.50
            )

            # For direct matches, we expect high confidence and correct type
            try:
                # Assertions for Category
                self.assertEqual(
                    prediction["drum_category"]["value"], expected_category,
                    f"Failed category for {expected_combo}: Predicted {prediction['drum_category']['value']}"
                )
                self.assertGreaterEqual(
                    prediction["drum_category"]["confidence"], 0.70,
                    f"Low category confidence for {expected_combo}: {prediction['drum_category']['confidence']:.2f}")

                # Assertions for Type
                self.assertEqual(
                    prediction["drum_type"]["value"], expected_type,
                    f"Failed for {expected_type}: Predicted {prediction['drum_type']['value']}"
                )
                self.assertGreaterEqual(
                    prediction["drum_type"]["confidence"], 0.50,
                    f"Low confidence for {expected_type}: {prediction['drum_type']['confidence']:2f}"
                )

                # Assertions for Qualifier
                self.assertEqual(
                    prediction["qualifier"]["value"], expected_qualifier,
                    f"Failed qualifier for {expected_combo}: Predicted {prediction['qualifier']['value']}")
                self.assertGreaterEqual(
                    prediction["qualifier"]["confidence"], 0.50,
                    f"Low qualifier confidence for {expected_combo}: {prediction['qualifier']['confidence']:.2f}")

                successful_classifications[expected_combo] += 1

            except AssertionError as e:
                print(f"\nClassification FAILURE for {expected_combo}: {e}")
                print(f"Sample Features: {test_sample}")
                print(f"Prediction: {prediction}")
                self.fail(f"Classification test failed for {expected_combo}: {e}")

        # Assert that all sampled combinations passed their individual
        # classification
        for expected_combo in samples_to_test_per_combo.keys():
            self.assertIn(
                expected_combo, successful_classifications,
                f"Type '{expected_combo}' was not successfully classified."
            )
            self.assertGreater(
                successful_classifications[expected_combo], 0,
                f"Type '{expected_combo}' had no successful classifications."
            )

    def test_classify_drum_events_list_with_real_data_and_confidence(self):
        """
        Test classification for a list of events using real data,
        checking hierarchical confidence filtering.
        """
        # Take a subset of real samples for the list, ensuring some
        # variety if possible.
        if len(self.real_known_samples) < 3:
            self.skipTest(
                "Not enough real samples to test list classification thoroughly."
            )

        # Pick 3 diverse samples. Ensure they have category/type/
        # qualifier set. Find samples that actually have these
        # properties for robust testing.
        test_list = []
        sample_indices = set()
        for i, sample in enumerate(self.real_known_samples):
            if sample.get("drum_category") and sample.get("drum_type") and i not in sample_indices:
                test_list.append(sample)
                sample_indices.add(i)
                if len(test_list) == 3:
                    break

        if len(test_list) < 3:
            self.skipTest("Could not find enough diverse real samples with full classification data to test list.")

        min_cat_conf = 0.7
        min_type_conf = 0.5
        min_qual_conf = 0.5

        init_args = (
            self.real_known_samples,
            self.mla.feature_weights,
            self.mla.drum_categories,
            self.mla.drum_types,
            self.mla.drum_qualifiers,
            self.mla._feature_ranges,
        )

        with ProcessPoolExecutor(initializer=_init_process_pool_worker, initargs=init_args) as test_executor:
            results = self.mla.classify_drum_events(
                test_list,
                min_category_confidence=min_cat_conf,
                min_type_confidence=min_type_conf,
                min_qualifier_confidence=min_qual_conf,
                k=5,
                executor=test_executor
            )

        self.assertEqual(len(results), len(test_list))

        for i, result in enumerate(results):
            original_category = test_list[i].get("drum_category")
            original_type = test_list[i].get("drum_type")
            original_qualifier = test_list[i].get("qualifier") if test_list[i].get("qualifier") is not None else "no_qualifier"

            self.assertIn("drum_category", result)
            self.assertIn("category_confidence", result)
            self.assertIn("drum_type", result)
            self.assertIn("type_confidence", result)
            self.assertIn("qualifier", result)
            self.assertIn("qualifier_confidence", result)

            if result["category_confidence"] >= min_cat_conf:
                self.assertEqual(result["drum_category"],
                                 original_category)
                if result["type_confidence"] >= min_type_conf:
                    self.assertEqual(result["drum_type"],
                                     original_type)
                    if result["qualifier_confidence"] >= min_qual_conf:
                        self.assertEqual(result["qualifier"],
                                         original_qualifier)
                    else:
                        self.assertEqual(result["qualifier"], "no_qualifier")
                else:
                    self.assertEqual(result["drum_type"],
                                     "unknown")
                    self.assertEqual(result["qualifier"], "no_qualifier")
            else:
                self.assertEqual(result["drum_category"],
                                 "other")
                self.assertEqual(result["drum_type"],
                                 "unknown")
                self.assertEqual(result["qualifier"],
                                 "no_qualifier")

            # Ensure original features are mostly preserved
            for key in list(self.mla.feature_weights.keys()) + ['onset_time', 'relative_volume', 'dominant_frequency', 'sample_name']:
                if key in test_list[i]:
                    if key == 'mfccs': # mfccs is converted to numpy array
                        self.assertIn(key, result)
                        self.assertIsInstance(result[key], list)
                        self.assertEqual(len(result[key]), 13)
                    elif isinstance(test_list[i][key], (float, int)):
                        self.assertAlmostEqual(
                            result[key], test_list[i][key],
                            places=5,
                            msg=f"List item {i} feature {key} mismatch."
                            )
                    else:
                        self.assertEqual(
                            result[key], test_list[i][key],
                            f"List item {i} feature {key} mismatch."
                        )

    def test_feature_exclusion(self):
        """
        Test that excluded features (onset_time, relative_volume,
        dominant_frequency) do not influence classification.
        """
        # Use one of the real known samples for this test
        if not self.real_known_samples:
            self.skipTest("No real known samples available to test feature exclusion.")

        # Get a copy of a real sample
        original_sample = None
        for s in self.real_known_samples:
            if s.get("drum_category") and s.get("drum_type"):
                original_sample = s.copy()
                break

        if original_sample is None:
            self.skipTest("Could not find a suitable sample with full classification data to test feature exclusion.")

        # Sample with excluded features drastically changed
        modified_sample = original_sample.copy()
        modified_sample["onset_time"] = 99.0
        modified_sample["relative_volume"] = 0.01
        modified_sample["dominant_frequency"] = 50.0

        prediction_original = self.mla.classify_drum_event(original_sample)
        prediction_modified = self.mla.classify_drum_event(modified_sample)

        # Assert that all levels of prediction are the same
        self.assertEqual(
            prediction_original["drum_category"]["value"],
            prediction_modified["drum_category"]["value"]
        )
        self.assertAlmostEqual(
            prediction_original["drum_category"]["confidence"],
            prediction_modified["drum_category"]["confidence"]
        )

        self.assertEqual(
            prediction_original["drum_type"]["value"],
            prediction_modified["drum_type"]["value"]
        )
        self.assertAlmostEqual(
            prediction_original["drum_type"]["confidence"],
            prediction_modified["drum_type"]["confidence"]
        )

        self.assertEqual(
            prediction_original["qualifier"]["value"],
            prediction_modified["qualifier"]["value"]
        )
        self.assertAlmostEqual(
            prediction_original["qualifier"]["confidence"],
            prediction_modified["qualifier"]["confidence"]
        )

        # Assert that it correctly classified the type based on the
        # real data
        self.assertEqual(
            prediction_original["drum_category"]["value"],
            original_sample["drum_category"])
        self.assertEqual(
            prediction_original["drum_type"]["value"],
            original_sample["drum_type"]
        )
        expected_qual = original_sample.get("qualifier") if original_sample.get("qualifier") is None else "no_qualifier"
        self.assertEqual(prediction_original["qualifier"]["value"],
                         expected_qual)

    def test_mfccs_malformed_input(self):
        """Test handling of malformed MFCCs in input."""
        # Use a real sample as base, then modify its MFCCs
        if not self.real_known_samples:
            self.skipTest("No real known samples available to test malformed MFCCs.")

        base_sample = self.real_known_samples[0].copy()

        # MFCCs with wrong length
        malformed_mfccs_len = base_sample.copy()
        malformed_mfccs_len["mfccs"] = [1.0] * 10 # Wrong length

        print(f"\n--- Testing malformed_mfccs_len ---")
        prediction_len = self.mla.classify_drum_event(malformed_mfccs_len)
        print(f"Prediction for malformed_mfccs_len: {prediction_len}")
        self.assertEqual(prediction_len["drum_category"]["value"],
                         "other")
        self.assertEqual(prediction_len["drum_category"]["confidence"],
                         0.0)
        self.assertEqual(prediction_len["drum_type"]["value"],
                         "unknown")
        self.assertEqual(prediction_len["drum_type"]["confidence"],
                         0.0)
        self.assertEqual(prediction_len["qualifier"]["value"],
                         "no_qualifier")
        self.assertEqual(prediction_len["qualifier"]["confidence"],
                         0.0)

        # MFCCs not a list of numbers
        malformed_mfccs_type = base_sample.copy()
        malformed_mfccs_type["mfccs"] = [1.0, "not_a_float"] + [1.0]*11 # Contains non-float

        print(f"\n--- Testing malformed_mfccs_type ---")
        prediction_type = self.mla.classify_drum_event(malformed_mfccs_type)
        self.assertEqual(prediction_type["drum_category"]["value"],
                         "other")
        self.assertEqual(prediction_type["drum_category"]["confidence"],
                         0.0)
        self.assertEqual(prediction_type["drum_type"]["value"],
                         "unknown")
        self.assertEqual(prediction_type["drum_type"]["confidence"],
                         0.0)
        self.assertEqual(prediction_type["qualifier"]["value"],
                         "no_qualifier")
        self.assertEqual(prediction_type["qualifier"]["confidence"],
                         0.0)

    def test_no_known_samples(self):
        """Test classification when no known samples are provided."""
        mla = DrumMLA() # Initialize without known samples
        prediction = mla.classify_drum_event(self.sample_extracted_feature)
        self.assertEqual(prediction["drum_category"]["value"],
                         "other")
        self.assertEqual(prediction["drum_category"]["confidence"],
                         0.0)
        self.assertEqual(prediction["drum_type"]["value"],
                         "unknown")
        self.assertEqual(prediction["drum_type"]["confidence"], 0.0)
        self.assertEqual(prediction["qualifier"]["value"],
                         "no_qualifier")
        self.assertEqual(prediction["qualifier"]["confidence"], 0.0)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
