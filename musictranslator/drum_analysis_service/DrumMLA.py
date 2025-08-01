"""
Machine Learning Algorithm for predicting type of drum based on
known samples of spectral_centroid, spectral_rolloff, spectral_flux,
and duration.
"""
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from scipy.spatial.distance import euclidean

# Define module-level globals that will be populated by the
# initializer in each worker process
_global_known_samples = None
_global_feature_weights = None
_global_feature_ranges = None
_global_drum_categories = None
_global_drum_types = None
_global_drum_qualifiers = None

def _classify_drum_event_worker(task_args):
    """
    A top-level function that runs in a worker process. It creates
    a lightweight DrumMLA instance to access the classification logic,
    which in turn uses the global data loaded by the initializer.
    """
    extracted_features, mc_conf, mt_conf, mq_conf, k = task_args
    # This instance is lightweight; its own state is not used.
    # The classification methods it calls have been modified to use
    # the global data.
    temp_drum_mla = DrumMLA()
    return temp_drum_mla.classify_drum_event(
        extracted_features, mc_conf, mt_conf, mq_conf, k
    )

class DrumMLA:
    def __init__(self, known_samples_data=None):
        """
        Initializes the DrumMLA with known drum sample features.
        known_samples_data: A list of dictionaries, where
                            each dictionary represents a known drum
                            sample with its features and 'drum_type'.
        """
        # Stores known samples,hierarchically:
        # { 'drum_category_A': {
        #       'drum_type_X': {
        #           'qualifier_P':[ { 'features': np.array, 'original_data': {...} }, ... ],
        #           'qualifier_Q': [...]
        #       },
        #       'drum_type_Y': {...}
        #   },
        #   'drum_type_B': {...}
        # }
        # Features to be used for comparison, with weights
        # Higher weight means more important
        self.feature_weights = {
            'spectral_centroid': 1.0,
            'spectral_rolloff': 1.0,
            'spectral_flux': 1.0,
            'mfccs': 2.0,
            'duration': 0.5,
        }
        # Define the hierarchical structure of drum classifications
        self.drum_categories = ['kick', 'snare', 'tom', 'cymbal', 'other']
        self.drum_types = {
            'kick': ['bass'],
            'snare': ['open_band', 'closed_band'],
            'tom': ['med_high', 'med_low', 'mid', 'low', 'high'],
            'cymbal': ['crash', 'hihat', 'ride', 'gong', 'unknown'],
            'other': ['cowbell', 'unknown']
        }
        self.drum_qualifiers = {
            'snare': ['rimshot', 'brush', 'chains', 'no_qualifier'],
            'tom': ['rimshot', 'brush', 'chains', 'no_qualifier'],
            'kick': ['no_qualifier'],
            'other': ['no_qualifier', 'muted', 'brush', 'chains'],

            'cymbal': {
                'crash': ['full', 'mid', 'bell', 'muted', 'brush', 'chains', 'no_qualifier',
                          'full_muted', 'mid_muted', 'bell_muted',
                          'full_brush', 'mid_brush', 'bell_brush',
                          'full_chains', 'mid_chains', 'bell_chains',
                          'brush_muted', 'chains_muted',
                          'bell_brush_muted', 'bell_chains_muted',
                          'mid_brush_muted', 'mid_chains_muted',
                          'full_brush_muted', 'full_chains_muted',
                          'brush_bell', 'chains_bell',
                          'brush_full', 'chains_full',
                          'brush_mid', 'chains_mid',
                          'brush_bell_muted', 'chains_bell_muted',
                          'brush_full_muted', 'chains_full_muted',
                          'brush_mid_muted', 'chains_mid_muted',
                        ],
                'hihat': ['open', 'close', 'muted', 'brush', 'chains', 'no_qualifier',
                          'open_muted', 'close_muted',
                          'open_brush', 'open_chains',
                          'close_brush', 'close_chains',
                          'brush_muted', 'chains_muted',
                          'brush_open', 'brush_close',
                          'chains_open', 'chains_close',
                          'brush_muted_open', 'brush_muted_close',
                          'chains_muted_open', 'chains_muted_close'
                        ],
                'ride': ['bell', 'mid', 'muted', 'no_qualifier', 'brush', 'chains',
                         'bell_muted', 'mid_muted',
                         'bell_brush', 'mid_brush',
                         'bell_chains', 'mid_chains',
                         'brush_muted', 'chains_muted',
                         'brush_bell', 'chains_bell',
                         'brush_mid', 'chains_mid',
                         'brush_bell_muted', 'chains_bell_muted',
                         'brush_mid_muted', 'chains_mid_muted',
                        ],
                'gong': ['muted', 'brush', 'chains', 'no_qualifier',
                         'brush_muted', 'chains_muted'
                        ],
                'unknown': ['full', 'mid', 'bell', 'muted', 'brush',
                            'chains', 'no_qualifier',
                            'full_muted', 'mid_muted', 'bell_muted',
                            'full_brush', 'mid_brush', 'bell_brush',
                            'full_chains', 'mid_chains',
                            'bell_chains', 'brush_muted',
                            'chains_muted', 'bell_brush_muted',
                            'bell_chains_muted', 'mid_brush_muted',
                            'mid_chains_muted', 'full_brush_muted',
                            'full_chains_muted', 'brush_bell',
                            'chains_bell', 'brush_full',
                            'chains_full', 'brush_mid', 'chains_mid',
                            'brush_bell_muted', 'chains_bell_muted',
                            'brush_full_muted', 'chains_full_muted',
                            'brush_mid_muted', 'chains_mid_muted',
                          ]
            }
        }

        # Normalization/Standarization parameters
        # In the future, this will be trained on a larger dataset.
        # For now, we'll use a simple min-max scaling or pre-defined
        # ranges. For now, we'll keep it simple and just use raw
        # values, and consider normalization in a later iteration if
        # needed for better performance.
        self._feature_ranges = {}

        if known_samples_data:
            self.known_samples = DrumMLA._prepare_known_samples_from_raw(
                known_samples_data,
                self.drum_categories,
                self.drum_types,
                self.drum_qualifiers,
                self.feature_weights
            )
            self._calculate_normalization_parameters()
        else:
            self.known_samples = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    @staticmethod
    def _prepare_known_samples_from_raw(
        raw_samples, drum_categories, drum_types,
        drum_qualifiers, feature_weights
    ):
        """
        A static method to process raw sample data into the nested
        dictionary structure. This centralizes the preparation logic
        so it isn't duplicated.
        """
        prepared_samples = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for sample in raw_samples:
            # Make a copy to avoid modifying the original list of dicts
            sample_copy = sample.copy()

            drum_category = sample_copy.get("drum_category")
            drum_type = sample_copy.get("drum_type")
            qualifier = sample_copy.get("qualifier", "no_qualifier")
            if not qualifier:
                qualifier = "no_qualifier"

            # --- validation Logic

            if not drum_category or drum_category not in drum_categories:
                print(f"Warning: Sample has invalid or missing 'drum_category': {drum_category}. Skipping.")
                continue

            # Ensure drum_type is valid within the category, or default to 'unknown' if not provided
            if not drum_type:
                drum_type = "unknown"

            elif drum_category in drum_types and drum_type not in drum_types[drum_category]:
                drum_type = "unknown"

            # Ensure qualifier is valid within the type/category, or default to 'no_qualifier'
            if qualifier != "no_qualifier":
                allowed_qualifiers = []
                if drum_category in drum_qualifiers:
                    # Handle cymbal qualifiers which are nested by drum_type
                    if isinstance(drum_qualifiers[drum_category], dict):
                        allowed_qualifiers = drum_qualifiers[drum_category].get(drum_type, [])

                    else:
                        allowed_qualifiers = drum_qualifiers[drum_category]
                if qualifier not in allowed_qualifiers:
                    qualifier = "no_qualifier"

            prepared_features = {}
            if 'mfccs' not in sample_copy or not isinstance(sample_copy['mfccs'], list):
                continue

            for key, value in sample_copy.items():
                if key in feature_weights:
                    if key == 'mfccs':
                        prepared_features[key] = np.array(value, dtype=np.float32)
                    else:
                        prepared_features[key] = value

            if 'mfccs' in prepared_features:
                prepared_samples[drum_category][drum_type][qualifier].append(prepared_features)
        return prepared_samples

    def add_known_samples(self, new_samples):
        """
        Adds new known drum samples to the existing set.
        new_samples: A list of dictionaries, each with 'drum_category'
                     'drum_type', 'qualifier' (can be None), and
                     feature_data.
        """
        samples_added_count = 0
        for sample in new_samples:
            drum_category = sample.get("drum_category")
            drum_type = sample.get("drum_type")
            qualifier = sample.get("qualifier")

            if qualifier is None or qualifier == "":
                qualifier = "no_qualifier"

            if not drum_category or drum_category not in self.drum_categories:
                print(f"Warning: Sample has invalid or missing 'drum_category': {drum_category}. Skipping.")
                continue

            # Ensure drum_type is valid within the category, or default to 'unknown' if not provided
            if not drum_type:
                drum_type = "unknown"

            elif drum_category in self.drum_types and drum_type not in self.drum_types[drum_category]:
                if drum_type != "unknown": # Allow explicit 'unknown' drum_type
                    print(f"Warning: Drum type '{drum_type}' not defined for category '{drum_category}'. Defaulting to 'unknown' for this sample.")
                drum_type = "unknown"

            # Ensure qualifier is valid within the type/category, or default to 'no_qualifier'
            if qualifier != "no_qualifier":
                if drum_category not in self.drum_qualifiers:
                    print(f"Warning: Category '{drum_category}' does not support qualifiers. Defaulting to 'no_qualifier'.")
                    qualifier = "no_qualifier"
                else:
                    # Handle cymbal qualifiers which are nested by drum_type
                    if isinstance(self.drum_qualifiers[drum_category], dict):
                        # Check if the drum_type exists within the cymbal qualifiers
                        if drum_type in self.drum_qualifiers[drum_category]:
                            # Finally, check if the qualifier is valid
                            # for the specific cymbal drum_type
                            if qualifier not in self.drum_qualifiers[drum_category][drum_type]:
                                print(f"Warning: Qualifier '{qualifier}' not valid for drum type: '{drum_type}' in category: '{drum_category}'. Defaulting to 'no_qualifier'.")
                                qualifier = "no_qualifier"
                        else:
                            # If drum_type isn't found in the cymbal qualifier dict, it's invalid
                            print(f"Warning: Drum type '{drum_type}' not recognized for qualifier validation in category '{drum_category}'. Defaulting to 'no_qualifier'.")
                            qualifier = "no_qualifier"
                    # Handle non-cymbal qualifiers (list of qualifiers)
                    else:
                        if qualifier not in self.drum_qualifiers[drum_category]:
                            print(f"Warning: Qualifier '{qualifier}' not valid for category '{drum_category}'. Defaulting to 'no_qualifier'.")
                            qualifier = "no_qualifier"

            prepared_features = self._prepare_features(sample)
            # If prepared_features returns None, it means critical
            # data was malformed
            if prepared_features is None:
                print(f"Warning: Skipping sample due to malformed critical features (e.g., MFCCs): {sample.get('drum_category', 'unknown_category')}/{sample.get('drum_type', 'unknown_type')}.")
                continue

            self.known_samples[drum_category][drum_type][qualifier].append(prepared_features)
            samples_added_count += 1

        # Recalculate normalization parameters if new samples were added
        if samples_added_count > 0:
            self._calculate_normalization_parameters()

    # --- Helper Functions ---

    def _calculate_normalization_parameters(self):
        """
        Calculates min/max for each feature across all known samples.
        This should be called after all known smples are loaded or
        added.
        """
        if not self.known_samples:
            return

        all_features_flat = defaultdict(list)
        for drum_cat, types in self.known_samples.items():
            for drum_t, qualifiers in types.items():
                for qual, samples in qualifiers.items():
                    for sample_features in samples:
                        for key, value in sample_features.items():
                            if isinstance(value, np.ndarray):
                                if key == 'mfccs' and isinstance(value, np.ndarray):
                                    for mfcc_val in value: # For MFCCs
                                        all_features_flat['mfccs_coeff'].append(mfcc_val)
                            elif isinstance(value, (float, int)): # For scalar features
                                all_features_flat[key].append(value)

        self._feature_ranges = {}
        for feature_name, values in all_features_flat.items():
            if values:
                # Using min-max normalization for simplicity
                # Can upgrade to mean & standard deviation later
                self._feature_ranges[feature_name] = {
                    'min': np.min(values),
                    'max': np.max(values)
                }

    def _normalize_feature(self, feature_name, value):
        """
        Normalize a single feature value using stored min/max ranges.
        Upgrade to mean and standard deviation after more data points
        are added.
        """
        ranges = _global_feature_ranges if _global_feature_ranges is not None else self._feature_ranges

        base_feature_name = 'mfccs_coeff' if feature_name.startswith('mfccs_coeff') else feature_name

        if ranges and base_feature_name in ranges:
            f_min = ranges[base_feature_name]['min']
            f_max = ranges[base_feature_name]['max']
            if f_max > f_min:
                return (value - f_min) / (f_max - f_min)
        # If no range or division by zero, return original value
        # (or 0.0 depending on strategy)
        return value

    def _prepare_features(self, features_dict):
        """
        Internal helper to extract relevant features from an input
        dictionary. Returns a dictionary of prepared features, with
        mfccs as a numpy array. Excludes features listed in
        self.excluded_features. Returns None if critical features are malformed.
        """
        prepared = {}
        # Combine primary and secondary features for processing
        weights = _global_feature_weights if _global_feature_weights is not None else self.feature_weights
        features_to_process = weights.keys()

        for key in features_to_process:
            if key == 'mfccs':
                mfccs_data = features_dict.get('mfccs')
                if mfccs_data is not None:
                    # Ensure MFCCs are a list of 13 floats and convert to numpy array
                    if isinstance(mfccs_data, list) and len(mfccs_data) == 13 and \
                       all(isinstance(x, (float, int)) for x in mfccs_data):
                        prepared[key] = np.array(mfccs_data, dtype=np.float32)
                    else:
                        # Handle malformed MFCCs gracefully, e.g., by
                        # logging or setting to a default zero array
                        # to avoid errors. For now, let's treat it
                        # as missing.
                        print(f"Warning: Malformed MFCCs found for {features_dict.get('drum_type', 'unknown_sample')}. Treating as invalid")
                        return None
                else:
                    # Default if mfccs missing
                    print(f"Warning: Malformed MFCCs found for {features_dict.get('drum_type', 'unknown_sample')}. Treating as invalid.")
                    return None
            else:
                value = features_dict.get(key)
                if isinstance(value, (float, int)):
                    prepared[key] = float(value)
                else:
                    # Assign a default or handle missing/incorrect type (these are not MFCCs)
                    print(f"Warning: Feature '{key}' is missing or not numeric for {features_dict.get('drum_type', 'unknown_sample')}. Setting to 0.0.")
                    prepared[key] = 0.0

        return prepared

    def _calculate_weighted_distance(self, features1, features2):
        """
        Calculates a weighted Euclidean distance between two feature
        sets. features1, features2: dictionaries of prepared features
        """
        # If either feature set is None (due to malformed critical
        # features like MFCCs), return a very large distance to
        # ensure low confidence.
        if features1 is None or features2 is None:
            return np.inf

        distance = 0.0
        weights = _global_feature_weights if _global_feature_weights is not None else self.feature_weights

        for key, weight in weights.items():
            if key in features1 and key in features2:
                val1 = features1[key]
                val2 = features2[key]

                if key == 'mfccs':
                    if isinstance(val1, np.ndarray) and isinstance(val2, np.ndarray):
                        # Normalize each MFCC coefficient
                        normalized_mfccs1 = np.array([self._normalize_feature('mfccs_coeff', v) for v in val1])
                        normalized_mfccs2 = np.array([self._normalize_feature('mfccs_coeff', v) for v in val2])
                        distance += weight * euclidean(normalized_mfccs1, normalized_mfccs2)
                    else:
                        print(f"Warning: MFCCs are not numpy arrays for key '{key}' during distance calculation.")
                        distance += weight * 1000.0
                elif isinstance(val1, (float, int)) and isinstance(val2, (float, int)):
                    normalized_val1_scalar = self._normalize_feature(key, val1)
                    normalized_val2_scalar = self._normalize_feature(key, val2)
                    # For scalar features, calculate squared difference
                    distance += weight * ((normalized_val1_scalar - normalized_val2_scalar) ** 2)
                else:
                    print(f"Warning: Mismatched types for feature '{key}' during distance calculation.")
                    pass
        return np.sqrt(distance)

    def _get_k_nearest_neighbors(self, query_features, known_samples_subset, k):
        """
        Helper to find k-nearest neighbors within a specific subset of known samples.
        known_samples_subset: A list of prepared feature dictionaries to search within.
        Returns a sorted list of (distance, label) tuples for the k
        nearest neighbors.
        """
        distances = []
        for label_key, samples in known_samples_subset.items():
            for known_sample_features in samples:
                dist = self._calculate_weighted_distance(
                    query_features, known_sample_features
                )
                distances.append((dist, label_key))

        distances.sort(key=lambda x: x[0])
        return distances[:k]

    def _calculate_confidence(self, nearest_neighbors):
        """
        Calculates weighted confidence based on inverse distances of
        nearest neighbors.
        Returns (predicted_label, confidence).
        """
        if not nearest_neighbors:
            return "unknown", 0.0

        max_distance_in_neighbors = max([d for d, _ in nearest_neighbors]) + 1e-9

        votes = defaultdict(float)
        for dist, label in nearest_neighbors:
            # Scale distance to between 0 and 1 (0 is max_dist, 1 is
            # 0 dist). Use 1e-9 to avoid division by zero
            normalized_dist = dist / max_distance_in_neighbors

            weight = (1.0 - normalized_dist)
            votes[label] += weight

        if not votes:
            return "unknown", 0.0

        predicted_label = max(votes, key=votes.get)
        total_votes = sum(votes.values())
        confidence = votes[predicted_label] / total_votes if total_votes > 0 else 0.0

        return predicted_label, confidence


    # --- Hierarchical Classification Methods ---
    # These methods use the global parameters to prevent excessive
    # picking overhead.

    def _classify_category(self, extracted_features, k=5):
        """
        Classifies the drum category of the extracted features.
        Returns {'drum_category': str, 'confidence': float}.
        """
        prepared_extracted_features = self._prepare_features(extracted_features)
        if prepared_extracted_features is None:
            return {"value": "other", "confidence": 0.0}

        samples = _global_known_samples if _global_known_samples is not None else self.known_samples
        if not samples:
            return {"value": "other", "confidence": 0.0}

        # Flatten the known samples to just category level for initial
        # classification
        category_samples_flat = defaultdict(list)
        for drum_cat, types in samples.items():
            for drum_t, qualifiers in types.items():
                for qual, samples in qualifiers.items():
                    category_samples_flat[drum_cat].extend(samples)

        nearest_neighbors = self._get_k_nearest_neighbors(
            prepared_extracted_features, category_samples_flat, k
        )
        predicted_category, confidence = self._calculate_confidence(
            nearest_neighbors
        )

        return {
            "value": predicted_category,
            "confidence": confidence
        }

    def _classify_type_within_category(self, extracted_features, category, k=5):
        """
        Classifies the drum type within a given drum category.
        Returns {'drum_type': str, 'confidence': float}.
        """
        prepared_extracted_features = self._prepare_features(extracted_features)
        if prepared_extracted_features is None:
            return {"value": "unknown", "confidence": 0.0}

        samples = _global_known_samples if _global_known_samples is not None else self.known_samples
        if not samples:
            return {"value": "unknown", "confidence": 0.0}

        # Flatten the known samples within the given category to type level
        type_samples_flat = defaultdict(list)
        for drum_t, qualifiers in samples[category].items():
            for qual, samples in qualifiers.items():
                type_samples_flat[drum_t].extend(samples)

        nearest_neighbors = self._get_k_nearest_neighbors(
            prepared_extracted_features, type_samples_flat, k
        )
        predicted_type, confidence = self._calculate_confidence(
            nearest_neighbors
        )

        # If the predicted type is not in the allowed types for this
        # category, return 'unknown'
        drum_types_map = _global_drum_types if _global_drum_types is not None else self.drum_types
        if category in drum_types_map and predicted_type not in drum_types_map[category] and predicted_type != "unknown":
            return {"value": "unknown", "confidence": 0.0}

        return {"value": predicted_type, "confidence": confidence}

    def _classify_qualifier_within_type(
        self, extracted_features, category, drum_type, k=3):
        """
        Classifies the qualifier within a given drum category and
        drum type.
        Returns {'qualifier': str, 'confidence': float}.
        """
        prepared_extracted_features = self._prepare_features(extracted_features)
        if prepared_extracted_features is None:
            return {"value": "no_qualifier", "confidence": 0.0}

        samples = _global_known_samples if _global_known_samples is not None else self.known_samples
        if category not in samples or \
           drum_type not in samples[category] or \
           not samples[category][drum_type]:
            return {"value": "no_qualifier", "confidence": 0.0}

        # The known_samples[category][drum_type] is already a dictionary of qualifiers to lists of samples
        qualifiers_samples_dict = samples[category][drum_type]

        nearest_neighbors = self._get_k_nearest_neighbors(
            prepared_extracted_features, qualifiers_samples_dict, k
        )
        predicted_qualifier, confidence = self._calculate_confidence(
            nearest_neighbors
        )

        # If the predicted qualifier is not in the allowed qualifiers
        # for this type/category, return 'no_qualifier'
        allowed_qualifiers = []
        drum_qualifiers_map = _global_drum_qualifiers if _global_drum_qualifiers is not None else self.drum_qualifiers
        if category in drum_qualifiers_map:
            if isinstance(drum_qualifiers_map[category], dict): # Cymbals
                if drum_type in drum_qualifiers_map[category]:
                    allowed_qualifiers = drum_qualifiers_map[category][drum_type]
            else: # Other categories
                allowed_qualifiers = drum_qualifiers_map[category]

        if predicted_qualifier != "no_qualifier" and \
           predicted_qualifier not in allowed_qualifiers:
            return {"value": "no_qualifier", "confidence": 0.0}

        return {"value": predicted_qualifier, "confidence": confidence}

    # Re-expose the main classification method to maintain API
    def classify_drum_event(self, extracted_features,
                            min_category_confidence=0.7,
                            min_type_confidence=0.5,
                            min_qualifier_confidence=0.5, k=5):
        """
        Performs hierarchical classification for a single drum event:
        1. Classifies drum_category.
        2. Classifies drum_type within the predicted category.
        3. Classifes qualifier within the predicted category and type.
        Returns a dictionary with predicted category, type, qualifier,
        and their confidences.
        """
        results = extracted_features.copy()

        results["drum_category"] = {"value": "other", "confidence": 0.0}
        results["drum_type"] = {"value": "unknown", "confidence": 0.0}
        results["qualifier"] = {"value": "no_qualifier", "confidence": 0.0}

        # Step 1: Classify drum_category
        category_prediction = self._classify_category(extracted_features, k)
        results["drum_category"]["value"] = category_prediction["value"]
        results["drum_category"]["confidence"] = category_prediction["confidence"]

        # If category confidence is too low or not predicted, stop
        # here for sub-classifications. This confidence threshold can
        # be adjusted for early exit.
        if results["drum_category"]["confidence"] > min_category_confidence:
            # Step 2: Classify drum_type within the predicted category
            type_prediction = self._classify_type_within_category(
                extracted_features,
                results["drum_category"]["value"],
                k
            )
            results["drum_type"]["value"] = type_prediction["value"]
            results["drum_type"]["confidence"] = type_prediction["confidence"]

            # If drum_type confidence is too low or not predicted,
            # stop here for qualifier
            if results["drum_type"]["confidence"] > min_type_confidence:
                # Step 3: Classify qualifier within the predicted category and type
                qualifier_prediction = self._classify_qualifier_within_type(
                    extracted_features,
                    results["drum_category"]["value"],
                    results["drum_type"]["value"],
                    k
                )
                results["qualifier"]["value"] = qualifier_prediction["value"]
                results["qualifier"]["confidence"] = qualifier_prediction["confidence"]
            else:
                results["qualifier"]["value"] = "no_qualifier"
                results["qualifier"]["confidence"] = 0.0
        else:
            results["drum_type"]["value"] = "unknown"
            results["drum_type"]["confidence"] = 0.0
            results["qualifier"]["value"] = "no_qualifier"
            results["qualifier"]["confidence"] = 0.0

        return results

    # This now uses _global_classify_drum_event_for_pool which is
    # defined in app.py. The key is that the 'classify_drum_event'
    # method of the DrumMLA instance that resides in the Flask
    # worker is the one calling ProcessPoolExecutor. The
    # `_global_classify_drum_event_for_pool` function is what's
    # actually sent to the child process.
    def classify_drum_events(
        self, list_of_extracted_features,
        min_category_confidence=0.7,
        min_type_confidence=0.5,
        min_qualifier_confidence=0.5,
        k=5,
        executor=None
    ):
        """
        Processes a list of extracted drum feature sets, adding
        'drum_category', 'drum_type', 'qualifier' and their respective
        confidences to each. Thresholds can be set for each level.
        """
        classified_events = []

        if not list_of_extracted_features:
            return []
        if executor is None:
            # Fallback to sequential execution if no executor is provided
            for features in list_of_extracted_features:
                prediction = self.classify_drum_event(
                    features, min_category_confidence,
                    min_type_confidence, min_qualifier_confidence, k
                )
                if 'mfccs' in prediction and isinstance(prediction['mfccs'], np.ndarray):
                    prediction['mfccs'] = prediction['mfccs'].tolist()

                formatted_prediction = {
                    "drum_category": prediction["drum_category"]["value"],
                    "category_confidence": prediction["drum_category"]["confidence"],
                    "drum_type": prediction["drum_type"]["value"],
                    "type_confidence": prediction["drum_type"]["confidence"],
                    "qualifier": prediction["qualifier"]["value"],
                    "qualifier_confidence": prediction["qualifier"]["confidence"]
                }
                for key, value in prediction.items():
                    if key not in ["drum_category", "drum_type", "qualifier"]:
                        formatted_prediction[key] = value
                classified_events.append(formatted_prediction)
            return classified_events

        # Prepare tasks for the process pool. Each task is a tuple of
        # all arguments
        tasks = [
            (features, min_category_confidence, min_type_confidence, min_qualifier_confidence, k)
            for features in list_of_extracted_features
        ]

        # Use the executor.map for a clean way to process the tasks
        results = executor.map(_classify_drum_event_worker, tasks)

        # Collect results as they complete
        for prediction in results:
            # Ensure NumPy arrays are converted to lists for JSON
            # serialization
            if 'mfccs' in prediction and isinstance(
                prediction['mfccs'], np.ndarray
            ):
                prediction['mfccs'] = prediction['mfccs'].tolist()

            # Reconstruct the output format
            formatted_prediction = {
                "drum_category": prediction["drum_category"]["value"],
                "category_confidence": prediction["drum_category"]["confidence"],
                "drum_type": prediction["drum_type"]["value"],
                "type_confidence": prediction["drum_type"]["confidence"],
                "qualifier": prediction["qualifier"]["value"],
                "qualifier_confidence": prediction["qualifier"]["confidence"],
            }
            # Add all other original features that were part of
            # the 'prediction' dict
            for key, value in prediction.items():
                if key not in ["drum_category", "drum_type", "qualifier"]:
                    formatted_prediction[key] = value

            classified_events.append(formatted_prediction)

        return classified_events
